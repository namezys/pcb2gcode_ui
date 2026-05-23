import logging
import math
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from pygerber.gerberx3.api.v2 import (
    ColorScheme,
    FileTypeEnum,
    GerberFile,
    ImageFormatEnum,
    ParsedFile,
    PixelFormatEnum,
)

from pcb2gcode_ui.gcode_preview import (
    GcodeMovementKind,
    GcodeTrace,
    gcode_instrument_color,
    gcode_tool_path_id,
)
from pcb2gcode_ui.options import bool_value

LOGGER = logging.getLogger(__name__)
DEFAULT_PREVIEW_DPMM = 100
DEFAULT_LAYER_ALPHA = 50
MAX_ALPHA = 255
MIN_CANVAS_SIZE = 1
MAX_PREVIEW_PIXELS = 50_000_000
BOARD_PADDING_MM = 2.0
DEFAULT_DRILL_DIAMETER_MM = 0.8
COORDINATE_RE = re.compile(r"(?P<axis>[XY])(?P<value>[+-]?\d+(?:\.\d+)?)")
TOOL_RE = re.compile(r"^T(?P<id>\d+)(?:C(?P<diameter>[+-]?\d+(?:\.\d+)?))?")
DRILL_FORMAT_RE = re.compile(r"(?<!\d)(?P<integer>0+)\.(?P<decimal>0+)(?!\d)")
GERBER_FORMAT_RE = re.compile(
    r"%FSLAX(?P<x_integer>\d)(?P<x_decimal>\d)Y(?P<y_integer>\d)(?P<y_decimal>\d)\*%"
)
GERBER_APERTURE_RE = re.compile(
    r"%ADD(?P<id>\d+)C,(?P<diameter>[+-]?\d+(?:\.\d+)?)\*%"
)
GERBER_D_CODE_RE = re.compile(r"^D(?P<id>\d+)\*$")
GERBER_COORDINATE_RE = re.compile(
    r"^(?:X(?P<x>[+-]?\d+))?(?:Y(?P<y>[+-]?\d+))?D(?P<operation>0[12])\*$"
)
UNIT_MM = "mm"
UNIT_INCH = "inch"
GCODE_CUT_ALPHA = 235
GCODE_RETRACT_ALPHA = 115


class PreviewSide(StrEnum):
    FRONT = "front"
    BACK = "back"


class PreviewLayerKind(StrEnum):
    FRONT = "front"
    BACK = "back"
    DRILL = "drill"
    CUTOFF = "cutoff"
    AUX = "aux"


@dataclass(frozen=True)
class PreviewOptions:
    side: PreviewSide = PreviewSide.FRONT
    show_front: bool = True
    show_back: bool = False
    show_drill: bool = True
    show_cutoff: bool = True
    show_aux: bool = True
    show_gcode: bool = False
    aux_layer: Path = None
    gcode_trace: GcodeTrace = None
    layer_alpha: int = DEFAULT_LAYER_ALPHA
    dpmm: int = DEFAULT_PREVIEW_DPMM


@dataclass(frozen=True)
class PreviewResult:
    png: bytes
    warnings: list[str]
    layer_count: int

    @property
    def ok(self) -> bool:
        return bool(self.png)


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def expand(self, other: "Bounds") -> "Bounds":
        return Bounds(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )


@dataclass(frozen=True)
class GerberLayer:
    path: Path
    kind: PreviewLayerKind
    file_type: FileTypeEnum
    color_scheme: ColorScheme


@dataclass(frozen=True)
class RenderedLayer:
    image: Image.Image
    kind: PreviewLayerKind
    bounds: Bounds


@dataclass(frozen=True)
class CachedParsedFile:
    parsed_file: ParsedFile
    modified_ns: int
    size: int


@dataclass(frozen=True)
class DrillHit:
    x_mm: float
    y_mm: float
    diameter_mm: float


@dataclass(frozen=True)
class DrillLayer:
    hits: list[DrillHit]
    warnings: list[str]


@dataclass
class DrillFormat:
    unit: str = UNIT_INCH
    decimal_places: int = 0


@dataclass
class GerberFormat:
    unit: str = UNIT_INCH
    x_decimal_places: int = 0
    y_decimal_places: int = 0


@dataclass(frozen=True)
class GerberSegment:
    start_x_mm: float
    start_y_mm: float
    end_x_mm: float
    end_y_mm: float
    diameter_mm: float


@dataclass(frozen=True)
class TransformSettings:
    metric: bool
    zero_start: bool
    x_offset_mm: float
    y_offset_mm: float
    tile_x: int
    tile_y: int
    board_bounds: Bounds


class GerberPreviewRenderer:
    def __init__(self):
        self.parsed_files: dict[Path, CachedParsedFile] = {}

    def render(
        self,
        values: dict[str, str],
        base_dir: Path,
        options: PreviewOptions,
    ) -> PreviewResult:
        LOGGER.debug("Rendering preview with options %r", options)
        warnings: list[str] = []
        gerber_layers = _collect_gerber_layers(values, base_dir, options, warnings)
        drill_layer = _collect_drill_layer(values, base_dir, options, warnings)
        gcode_trace = options.gcode_trace if options.show_gcode else None
        if not gerber_layers and not drill_layer and not _has_gcode(gcode_trace):
            return PreviewResult(b"", warnings or ["No visible preview layers."], 0)

        rendered_layers = self._render_gerber_layers(gerber_layers, options, warnings)
        source_bounds = _source_bounds(rendered_layers, drill_layer, gcode_trace)
        if not source_bounds:
            return PreviewResult(b"", warnings or ["No renderable preview content."], 0)

        settings = _transform_settings(values, source_bounds)
        transformed_bounds = _transformed_bounds(
            rendered_layers,
            drill_layer,
            settings,
            gcode_trace,
        )
        if not transformed_bounds:
            return PreviewResult(b"", warnings or ["No renderable preview content."], 0)

        width_px, height_px, pixel_count = _preview_canvas_size(
            transformed_bounds,
            settings,
            options,
        )
        LOGGER.debug(
            "Preview bounds %r at %s dpmm produce canvas %sx%s (%s pixels)",
            transformed_bounds,
            options.dpmm,
            width_px,
            height_px,
            pixel_count,
        )
        if pixel_count > MAX_PREVIEW_PIXELS:
            warning = (
                f"Preview canvas is too large ({width_px}x{height_px} pixels). "
                "Check drill coordinate format or lower preview quality."
            )
            LOGGER.warning("%s", warning)
            return PreviewResult(b"", [*warnings, warning], 0)

        image = _compose_preview(
            rendered_layers,
            drill_layer,
            transformed_bounds,
            settings,
            options,
            gcode_trace,
        )
        png = _png_bytes(image)
        layer_count = (
            len(rendered_layers)
            + (1 if drill_layer and drill_layer.hits else 0)
            + (1 if _has_gcode(gcode_trace) else 0)
        )
        return PreviewResult(png, warnings, layer_count)

    def _render_gerber_layers(
        self,
        layers: list[GerberLayer],
        options: PreviewOptions,
        warnings: list[str],
    ) -> list[RenderedLayer]:
        rendered_layers: list[RenderedLayer] = []
        for layer in layers:
            try:
                parsed_file = self._parse(layer.path, layer.file_type)
                bounds = _bounds_from_parsed_file(parsed_file)
                image = _render_parsed_file(parsed_file, layer.color_scheme, options.dpmm)
                image = _tint_layer_image(image, _layer_color(layer.kind))
                rendered_layers.append(
                    RenderedLayer(
                        image=image,
                        kind=layer.kind,
                        bounds=bounds,
                    )
                )
            except Exception as error:
                if layer.kind == PreviewLayerKind.CUTOFF:
                    fallback_layer = _render_cutoff_fallback(layer.path, options, error)
                    if fallback_layer:
                        rendered_layers.append(fallback_layer)
                        continue
                LOGGER.exception("Failed to render Gerber preview for %r", layer.path)
                warnings.append(f"Could not render {layer.path.name}: {error}")
        return rendered_layers

    def _parse(self, path: Path, file_type: FileTypeEnum) -> ParsedFile:
        resolved_path = path.resolve()
        stat_result = resolved_path.stat()
        cached_file = self.parsed_files.get(resolved_path)
        if (
            cached_file
            and cached_file.modified_ns == stat_result.st_mtime_ns
            and cached_file.size == stat_result.st_size
        ):
            return cached_file.parsed_file
        LOGGER.debug("Parsing Gerber preview file %r", resolved_path)
        parsed_file = GerberFile.from_file(resolved_path, file_type).parse()
        self.parsed_files[resolved_path] = CachedParsedFile(
            parsed_file=parsed_file,
            modified_ns=stat_result.st_mtime_ns,
            size=stat_result.st_size,
        )
        return parsed_file


def _collect_gerber_layers(
    values: dict[str, str],
    base_dir: Path,
    options: PreviewOptions,
    warnings: list[str],
) -> list[GerberLayer]:
    layers: list[GerberLayer] = []
    if options.show_front:
        path = _path_value(values, "front", base_dir)
        if path:
            layers.append(
                GerberLayer(
                    path,
                    PreviewLayerKind.FRONT,
                    FileTypeEnum.COPPER,
                    ColorScheme.DEFAULT_GRAYSCALE,
                )
            )
        else:
            warnings.append("No front Gerber file selected.")
    if options.show_back:
        path = _path_value(values, "back", base_dir)
        if path:
            layers.append(
                GerberLayer(
                    path,
                    PreviewLayerKind.BACK,
                    FileTypeEnum.COPPER,
                    ColorScheme.DEFAULT_GRAYSCALE,
                )
            )
        else:
            warnings.append("No back Gerber file selected.")
    if options.show_cutoff:
        path = _path_value(values, "outline", base_dir)
        if path:
            layers.append(
                GerberLayer(
                    path,
                    PreviewLayerKind.CUTOFF,
                    FileTypeEnum.EDGE,
                    ColorScheme.DEFAULT_GRAYSCALE,
                )
            )
    if options.show_aux and options.aux_layer:
        layers.append(
            GerberLayer(
                _resolve_path(str(options.aux_layer), base_dir),
                PreviewLayerKind.AUX,
                FileTypeEnum.INFER,
                ColorScheme.DEFAULT_GRAYSCALE,
            )
        )
    return layers


def _collect_drill_layer(
    values: dict[str, str],
    base_dir: Path,
    options: PreviewOptions,
    warnings: list[str],
) -> DrillLayer | None:
    if not options.show_drill:
        return None
    path = _path_value(values, "drill", base_dir)
    if not path:
        return None
    drill_layer = _parse_drill_file(path)
    warnings.extend(drill_layer.warnings)
    return drill_layer


def _parse_drill_file(path: Path) -> DrillLayer:
    warnings: list[str] = []
    hits: list[DrillHit] = []
    tools: dict[str, float] = {}
    active_tool = ""
    drill_format = DrillFormat()
    current_x: float = None
    current_y: float = None
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as error:
        return DrillLayer([], [f"Could not read drill file {path.name}: {error}"])

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip().upper()
        if not line or line.startswith(";"):
            continue
        if "METRIC" in line or line == "M71":
            drill_format.unit = UNIT_MM
            _update_drill_decimal_places(line, drill_format)
            continue
        if "INCH" in line or line == "M72":
            drill_format.unit = UNIT_INCH
            _update_drill_decimal_places(line, drill_format)
            continue
        _update_drill_decimal_places(line, drill_format)
        tool_match = TOOL_RE.match(line)
        if tool_match:
            tool_id = tool_match.group("id")
            diameter = tool_match.group("diameter")
            active_tool = tool_id
            if diameter:
                tools[tool_id] = _unit_to_mm(float(diameter), drill_format.unit)
            continue
        coordinate_values = {
            match.group("axis"): match.group("value")
            for match in COORDINATE_RE.finditer(line)
        }
        if not coordinate_values:
            continue
        if "X" in coordinate_values:
            current_x = _drill_coordinate_to_mm(coordinate_values["X"], drill_format)
        if "Y" in coordinate_values:
            current_y = _drill_coordinate_to_mm(coordinate_values["Y"], drill_format)
        if current_x is None or current_y is None:
            warnings.append(f"Skipping drill hit without X/Y at line #{line_number}.")
            continue
        diameter_mm = tools.get(active_tool, DEFAULT_DRILL_DIAMETER_MM)
        if not active_tool:
            warnings.append(f"Using default drill diameter at line #{line_number}.")
        hits.append(DrillHit(current_x, current_y, diameter_mm))
    if hits:
        LOGGER.debug(
            "Parsed %s drill hit(s) from %r with bounds %r",
            len(hits),
            path,
            _drill_bounds(hits),
        )
    return DrillLayer(hits, warnings)


def _update_drill_decimal_places(line: str, drill_format: DrillFormat):
    format_match = DRILL_FORMAT_RE.search(line)
    if format_match:
        drill_format.decimal_places = len(format_match.group("decimal"))


def _drill_coordinate_to_mm(value: str, drill_format: DrillFormat) -> float:
    if "." in value:
        coordinate = float(value)
    else:
        coordinate = int(value) / 10**drill_format.decimal_places
    return _unit_to_mm(coordinate, drill_format.unit)


def _render_cutoff_fallback(
    path: Path,
    options: PreviewOptions,
    parse_error: Exception,
) -> RenderedLayer | None:
    try:
        segments = _parse_gerber_segments(path)
    except OSError as error:
        LOGGER.warning("Could not read cutoff fallback file %r: %s", path, error)
        return None
    if not segments:
        LOGGER.debug(
            "No cutoff fallback segments found for %r after PyGerber error %r",
            path,
            parse_error,
        )
        return None
    bounds = _segment_bounds(segments)
    width_px = max(math.ceil(bounds.width * options.dpmm), MIN_CANVAS_SIZE)
    height_px = max(math.ceil(bounds.height * options.dpmm), MIN_CANVAS_SIZE)
    image = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = (*_layer_color(PreviewLayerKind.CUTOFF), MAX_ALPHA)
    for segment in segments:
        line_width = max(round(segment.diameter_mm * options.dpmm), 1)
        draw.line(
            (
                (segment.start_x_mm - bounds.min_x) * options.dpmm,
                (bounds.max_y - segment.start_y_mm) * options.dpmm,
                (segment.end_x_mm - bounds.min_x) * options.dpmm,
                (bounds.max_y - segment.end_y_mm) * options.dpmm,
            ),
            fill=color,
            width=line_width,
        )
    LOGGER.debug(
        "Rendered cutoff fallback for %r with %s segment(s) and bounds %r",
        path,
        len(segments),
        bounds,
    )
    return RenderedLayer(image, PreviewLayerKind.CUTOFF, bounds)


def _parse_gerber_segments(path: Path) -> list[GerberSegment]:
    gerber_format = GerberFormat()
    apertures: dict[str, float] = {}
    active_aperture = ""
    current_x_mm: float = None
    current_y_mm: float = None
    segments: list[GerberSegment] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip().upper()
        if not line:
            continue
        if line == "%MOMM*%":
            gerber_format.unit = UNIT_MM
            continue
        if line == "%MOIN*%":
            gerber_format.unit = UNIT_INCH
            continue
        format_match = GERBER_FORMAT_RE.match(line)
        if format_match:
            gerber_format.x_decimal_places = int(format_match.group("x_decimal"))
            gerber_format.y_decimal_places = int(format_match.group("y_decimal"))
            continue
        aperture_match = GERBER_APERTURE_RE.match(line)
        if aperture_match:
            apertures[aperture_match.group("id")] = _unit_to_mm(
                float(aperture_match.group("diameter")),
                gerber_format.unit,
            )
            continue
        d_code_match = GERBER_D_CODE_RE.match(line)
        if d_code_match:
            active_aperture = d_code_match.group("id")
            continue
        coordinate_match = GERBER_COORDINATE_RE.match(line)
        if not coordinate_match:
            continue
        next_x_mm = current_x_mm
        next_y_mm = current_y_mm
        if coordinate_match.group("x"):
            next_x_mm = _gerber_coordinate_to_mm(
                coordinate_match.group("x"),
                gerber_format.x_decimal_places,
                gerber_format.unit,
            )
        if coordinate_match.group("y"):
            next_y_mm = _gerber_coordinate_to_mm(
                coordinate_match.group("y"),
                gerber_format.y_decimal_places,
                gerber_format.unit,
            )
        if next_x_mm is None or next_y_mm is None:
            continue
        if (
            coordinate_match.group("operation") == "01"
            and current_x_mm is not None
            and current_y_mm is not None
        ):
            segments.append(
                GerberSegment(
                    current_x_mm,
                    current_y_mm,
                    next_x_mm,
                    next_y_mm,
                    apertures.get(active_aperture, DEFAULT_DRILL_DIAMETER_MM),
                )
            )
        current_x_mm = next_x_mm
        current_y_mm = next_y_mm
    return segments


def _gerber_coordinate_to_mm(value: str, decimal_places: int, unit: str) -> float:
    coordinate = int(value) / 10**decimal_places
    return _unit_to_mm(coordinate, unit)


def _segment_bounds(segments: list[GerberSegment]) -> Bounds:
    min_x = min(
        min(segment.start_x_mm, segment.end_x_mm) - segment.diameter_mm / 2
        for segment in segments
    )
    min_y = min(
        min(segment.start_y_mm, segment.end_y_mm) - segment.diameter_mm / 2
        for segment in segments
    )
    max_x = max(
        max(segment.start_x_mm, segment.end_x_mm) + segment.diameter_mm / 2
        for segment in segments
    )
    max_y = max(
        max(segment.start_y_mm, segment.end_y_mm) + segment.diameter_mm / 2
        for segment in segments
    )
    return Bounds(min_x, min_y, max_x, max_y)


def _render_parsed_file(
    parsed_file: ParsedFile,
    color_scheme: ColorScheme,
    dpmm: int,
) -> Image.Image:
    destination = BytesIO()
    parsed_file.render_raster(
        destination,
        color_scheme=color_scheme,
        dpmm=dpmm,
        image_format=ImageFormatEnum.PNG,
        pixel_format=PixelFormatEnum.RGBA,
    )
    destination.seek(0)
    return Image.open(destination).convert("RGBA")


def _apply_alpha(image: Image.Image, alpha_percent: int) -> Image.Image:
    alpha = _alpha_value(alpha_percent) / MAX_ALPHA
    red, green, blue, alpha_channel = image.split()
    alpha_channel = alpha_channel.point(lambda value: round(value * alpha))
    return Image.merge("RGBA", (red, green, blue, alpha_channel))


def _alpha_value(alpha_percent: int) -> int:
    return round(MAX_ALPHA * max(0, min(alpha_percent, 100)) / 100)


def _tint_layer_image(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    alpha_channel = image.getchannel("A")
    tinted = Image.new("RGBA", image.size, (*color, 0))
    tinted.putalpha(alpha_channel)
    return tinted


def _layer_color(kind: PreviewLayerKind) -> tuple[int, int, int]:
    if kind == PreviewLayerKind.FRONT:
        return (35, 220, 150)
    if kind == PreviewLayerKind.BACK:
        return (232, 74, 95)
    if kind == PreviewLayerKind.CUTOFF:
        return (235, 238, 242)
    return (80, 150, 255)


def _bounds_from_parsed_file(parsed_file: ParsedFile) -> Bounds:
    info = parsed_file.get_info()
    return Bounds(
        float(info.min_x_mm),
        float(info.min_y_mm),
        float(info.max_x_mm),
        float(info.max_y_mm),
    )


def _source_bounds(
    rendered_layers: list[RenderedLayer],
    drill_layer: DrillLayer | None,
    gcode_trace: GcodeTrace = None,
) -> Bounds | None:
    bounds: Bounds = None
    for layer in rendered_layers:
        bounds = layer.bounds if bounds is None else bounds.expand(layer.bounds)
    if drill_layer and drill_layer.hits:
        drill_bounds = _drill_bounds(drill_layer.hits)
        bounds = drill_bounds if bounds is None else bounds.expand(drill_bounds)
    if _has_gcode(gcode_trace):
        trace_bounds = _gcode_bounds(gcode_trace)
        bounds = trace_bounds if bounds is None else bounds.expand(trace_bounds)
    return bounds


def _drill_bounds(hits: list[DrillHit]) -> Bounds:
    min_x = min(hit.x_mm - hit.diameter_mm / 2 for hit in hits)
    min_y = min(hit.y_mm - hit.diameter_mm / 2 for hit in hits)
    max_x = max(hit.x_mm + hit.diameter_mm / 2 for hit in hits)
    max_y = max(hit.y_mm + hit.diameter_mm / 2 for hit in hits)
    return Bounds(min_x, min_y, max_x, max_y)


def _transform_settings(values: dict[str, str], board_bounds: Bounds) -> TransformSettings:
    metric = _preview_bool(values.get("metric", "false"))
    return TransformSettings(
        metric=metric,
        zero_start=_preview_bool(values.get("zero-start", "false")),
        x_offset_mm=_length_mm(values.get("x-offset", "0"), metric),
        y_offset_mm=_length_mm(values.get("y-offset", "0"), metric),
        tile_x=max(_int_value(values.get("tile-x", "1"), 1), 1),
        tile_y=max(_int_value(values.get("tile-y", "1"), 1), 1),
        board_bounds=board_bounds,
    )


def _transformed_bounds(
    rendered_layers: list[RenderedLayer],
    drill_layer: DrillLayer | None,
    settings: TransformSettings,
    gcode_trace: GcodeTrace = None,
) -> Bounds | None:
    bounds: Bounds = None
    for layer in rendered_layers:
        layer_bounds = _transform_bounds(layer.bounds, settings)
        bounds = layer_bounds if bounds is None else bounds.expand(layer_bounds)
    if drill_layer and drill_layer.hits:
        points = [
            _transform_point(hit.x_mm, hit.y_mm, settings)
            for hit in drill_layer.hits
        ]
        drill_bounds = Bounds(
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )
        bounds = drill_bounds if bounds is None else bounds.expand(drill_bounds)
    if _has_gcode(gcode_trace):
        points = [
            _transform_point(point.x_mm, point.y_mm, settings)
            for segment in gcode_trace.segments
            for point in (segment.start, segment.end)
        ]
        trace_bounds = Bounds(
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )
        bounds = trace_bounds if bounds is None else bounds.expand(trace_bounds)
    if bounds is None:
        return None
    return Bounds(
        bounds.min_x - BOARD_PADDING_MM,
        bounds.min_y - BOARD_PADDING_MM,
        bounds.max_x + BOARD_PADDING_MM,
        bounds.max_y + BOARD_PADDING_MM,
    )


def _transform_bounds(
    bounds: Bounds,
    settings: TransformSettings,
) -> Bounds:
    points = [
        _transform_point(bounds.min_x, bounds.min_y, settings),
        _transform_point(bounds.min_x, bounds.max_y, settings),
        _transform_point(bounds.max_x, bounds.min_y, settings),
        _transform_point(bounds.max_x, bounds.max_y, settings),
    ]
    return Bounds(
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _transform_point(
    x_value: float,
    y_value: float,
    settings: TransformSettings,
) -> tuple[float, float]:
    x_base = x_value - (settings.board_bounds.min_x if settings.zero_start else 0)
    y_base = y_value - (settings.board_bounds.min_y if settings.zero_start else 0)
    x_base += settings.x_offset_mm
    y_base += settings.y_offset_mm
    return x_base, y_base


def _compose_preview(
    rendered_layers: list[RenderedLayer],
    drill_layer: DrillLayer | None,
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
    gcode_trace: GcodeTrace = None,
) -> Image.Image:
    width_px = max(math.ceil(bounds.width * options.dpmm), MIN_CANVAS_SIZE)
    height_px = max(math.ceil(bounds.height * options.dpmm), MIN_CANVAS_SIZE)
    board_image = Image.new("RGBA", (width_px, height_px), (32, 35, 38, 255))
    for layer_kind in _layer_paint_order(options.side):
        if layer_kind == PreviewLayerKind.DRILL:
            if drill_layer and drill_layer.hits:
                _draw_drills(board_image, drill_layer, bounds, settings, options)
            continue
        for layer in rendered_layers:
            if layer.kind == layer_kind:
                _draw_rendered_layer(board_image, layer, bounds, settings, options)
    if options.show_gcode and _has_gcode(gcode_trace):
        _draw_gcode_trace(board_image, gcode_trace, bounds, settings, options)
    return _tile_image(board_image, settings.tile_x, settings.tile_y)


def _draw_rendered_layer(
    image: Image.Image,
    layer: RenderedLayer,
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
):
    layer_image = _apply_alpha(layer.image, _layer_alpha_percent(layer.kind, options))
    layer_bounds = _transform_bounds(layer.bounds, settings)
    left = round((layer_bounds.min_x - bounds.min_x) * options.dpmm)
    if _mirror_preview(options):
        layer_image = layer_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        left = image.width - left - layer_image.width
    top = round((bounds.max_y - layer_bounds.max_y) * options.dpmm)
    image.alpha_composite(layer_image, (left, top))


def _layer_paint_order(side: PreviewSide) -> tuple[PreviewLayerKind, ...]:
    if side == PreviewSide.BACK:
        return (
            PreviewLayerKind.FRONT,
            PreviewLayerKind.BACK,
            PreviewLayerKind.DRILL,
            PreviewLayerKind.CUTOFF,
            PreviewLayerKind.AUX,
        )
    return (
        PreviewLayerKind.BACK,
        PreviewLayerKind.FRONT,
        PreviewLayerKind.DRILL,
        PreviewLayerKind.CUTOFF,
        PreviewLayerKind.AUX,
    )


def _layer_alpha_percent(kind: PreviewLayerKind, options: PreviewOptions) -> int:
    if kind == PreviewLayerKind.FRONT and options.side == PreviewSide.FRONT:
        return options.layer_alpha
    if kind == PreviewLayerKind.BACK and options.side == PreviewSide.BACK:
        return options.layer_alpha
    return 100


def _mirror_preview(options: PreviewOptions) -> bool:
    return options.side == PreviewSide.BACK


def _preview_canvas_size(
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
) -> tuple[int, int, int]:
    width_px = max(math.ceil(bounds.width * options.dpmm), MIN_CANVAS_SIZE)
    height_px = max(math.ceil(bounds.height * options.dpmm), MIN_CANVAS_SIZE)
    tiled_width_px = width_px * settings.tile_x
    tiled_height_px = height_px * settings.tile_y
    return tiled_width_px, tiled_height_px, tiled_width_px * tiled_height_px


def _draw_drills(
    image: Image.Image,
    drill_layer: DrillLayer,
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
):
    draw = ImageDraw.Draw(image)
    drill_alpha = _alpha_value(options.layer_alpha)
    for hit in drill_layer.hits:
        x_value, y_value = _transform_point(hit.x_mm, hit.y_mm, settings)
        radius = max(hit.diameter_mm * options.dpmm / 2, 2)
        if _mirror_preview(options):
            x_value = bounds.max_x - x_value + bounds.min_x
        center_x = (x_value - bounds.min_x) * options.dpmm
        center_y = (bounds.max_y - y_value) * options.dpmm
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            fill=(87, 178, 255, drill_alpha),
            outline=(220, 245, 255, 255),
            width=1,
        )


def _draw_gcode_trace(
    image: Image.Image,
    trace: GcodeTrace,
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
):
    draw = ImageDraw.Draw(image)
    tool_path_colors = {
        tool_path.id: _hex_to_rgba(gcode_instrument_color(idx), GCODE_CUT_ALPHA)
        for idx, tool_path in enumerate(trace.active_tool_paths)
    }
    for segment in trace.segments:
        start = _preview_point(segment.start.x_mm, segment.start.y_mm, bounds, settings, options)
        end = _preview_point(segment.end.x_mm, segment.end.y_mm, bounds, settings, options)
        color = tool_path_colors.get(
            gcode_tool_path_id(segment.source_kind, segment.tool_id),
            _hex_to_rgba(gcode_instrument_color(0), GCODE_CUT_ALPHA),
        )
        if segment.movement == GcodeMovementKind.CUT:
            draw.line(
                (start, end),
                fill=color,
                width=max(round(options.dpmm * 0.08), 2),
            )
        else:
            _draw_dotted_line(
                draw,
                start,
                end,
                fill=(color[0], color[1], color[2], GCODE_RETRACT_ALPHA),
                width=max(round(options.dpmm * 0.04), 1),
                gap_px=max(round(options.dpmm * 0.35), 3),
            )


def _preview_point(
    x_value: float,
    y_value: float,
    bounds: Bounds,
    settings: TransformSettings,
    options: PreviewOptions,
) -> tuple[float, float]:
    transformed_x, transformed_y = _transform_point(x_value, y_value, settings)
    if _mirror_preview(options):
        transformed_x = bounds.max_x - transformed_x + bounds.min_x
    return (
        (transformed_x - bounds.min_x) * options.dpmm,
        (bounds.max_y - transformed_y) * options.dpmm,
    )


def _draw_dotted_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    fill: tuple[int, int, int, int],
    width: int,
    gap_px: int,
):
    distance_x = end[0] - start[0]
    distance_y = end[1] - start[1]
    line_length = math.hypot(distance_x, distance_y)
    if line_length == 0:
        return
    step = max(gap_px, 1)
    radius = max(width, 1)
    position = 0.0
    while position <= line_length:
        ratio = position / line_length
        center = (
            start[0] + distance_x * ratio,
            start[1] + distance_y * ratio,
        )
        draw.ellipse(
            (
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ),
            fill=fill,
        )
        position += step


def _hex_to_rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    normalized = color.removeprefix("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
        alpha,
    )


def _has_gcode(trace: GcodeTrace = None) -> bool:
    return bool(trace and trace.segments)


def _gcode_bounds(trace: GcodeTrace) -> Bounds:
    bounds = trace.bounds
    return Bounds(bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y)


def _tile_image(image: Image.Image, tile_x: int, tile_y: int) -> Image.Image:
    if tile_x == 1 and tile_y == 1:
        return image
    width, height = image.size
    tiled = Image.new("RGBA", (width * tile_x, height * tile_y), (32, 35, 38, 255))
    for row_idx in range(tile_y):
        for column_idx in range(tile_x):
            tiled.alpha_composite(image, (column_idx * width, row_idx * height))
    return tiled


def _png_bytes(image: Image.Image) -> bytes:
    destination = BytesIO()
    image.save(destination, format="PNG")
    return destination.getvalue()


def _path_value(values: dict[str, str], key: str, base_dir: Path) -> Path | None:
    value = values.get(key, "").strip()
    if not value:
        return None
    return _resolve_path(value, base_dir)


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(os.path.expanduser(value))
    if path.is_absolute():
        return path
    return base_dir / path


def _unit_to_mm(value: float, unit: str) -> float:
    if unit == UNIT_MM:
        return value
    return value * 25.4


def _length_mm(value: str, metric: bool) -> float:
    normalized = value.strip().lower()
    if not normalized or normalized == "inf":
        return 0
    try:
        if normalized.endswith("mm"):
            return float(normalized.removesuffix("mm"))
        if normalized.endswith("in"):
            return float(normalized.removesuffix("in")) * 25.4
        multiplier = 1 if metric else 25.4
        return float(normalized) * multiplier
    except ValueError:
        return 0


def _int_value(value: str, default: int) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return default


def _preview_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    try:
        return bool_value(value)
    except ValueError:
        return False
