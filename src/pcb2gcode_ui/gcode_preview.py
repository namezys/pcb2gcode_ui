import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gcodeparser import GcodeLine, parse_gcode_lines

from pcb2gcode_ui.options import default_output_directory

LOGGER = logging.getLogger(__name__)
UNIT_MM = "mm"
UNIT_INCH = "inch"
INCH_TO_MM = 25.4
DEFAULT_TOOL_ID = "none"
IMPLICIT_INSTRUMENT_ID = "implicit"
MOVEMENT_COMMANDS = {0, 1}
SUPPORTED_G_CODES = {0, 1, 20, 21, 90, 91}
SUPPORTED_M_CODES = {6}
COORDINATE_ONLY_RE = re.compile(r"^\s*[XYZFIJKR][+-]?\d", re.IGNORECASE)
TOOL_PARAMETER_RE = re.compile(
    r"Change\s+tool\s+bit\s+to\s+"
    r"(?P<tool_type>[A-Za-z][A-Za-z0-9_-]*)\s+"
    r"(?:diameter|size)\s+"
    r"(?P<diameter>[+-]?\d+(?:\.\d+)?\s*[A-Za-z]*)",
    re.IGNORECASE,
)
DIAMETER_RE = re.compile(r"(?P<number>[+-]?\d+(?:\.\d+)?)(?P<unit>[A-Za-z]*)")
OUTPUT_OPTIONS = (
    ("front", "front-output"),
    ("back", "back-output"),
    ("drill", "drill-output"),
    ("align-drill", "pre-align-drill-output"),
    ("milldrill", "milldrill-output"),
    ("outline", "outline-output"),
)
GCODE_INSTRUMENT_COLORS = (
    "#FFD64E",
    "#FF6987",
    "#5AD2FF",
    "#96B9FF",
    "#60D394",
    "#C084FC",
    "#FF9F1C",
    "#F2F5EA",
)
TOOLS_REPORT_NAME = "tools.md"


class GcodeMovementKind(StrEnum):
    CUT = "cut"
    RETRACT = "retract"


@dataclass(frozen=True)
class GcodeToolParameters:
    tool_type: str
    diameter: str


@dataclass(frozen=True)
class GcodePoint:
    x_mm: float
    y_mm: float
    z_mm: float


@dataclass(frozen=True)
class GcodeSegment:
    start: GcodePoint
    end: GcodePoint
    movement: GcodeMovementKind
    tool_id: str
    source_kind: str
    line_number: int
    instrument_id: str = IMPLICIT_INSTRUMENT_ID
    source_label: str = ""


@dataclass(frozen=True)
class GcodeInstrument:
    id: str
    tool_id: str
    source_kind: str
    change_index: int
    line_number: int
    parameters: GcodeToolParameters = None


@dataclass(frozen=True)
class GcodeSource:
    kind: str
    label: str


@dataclass(frozen=True)
class GcodeToolPath:
    id: str
    tool_id: str
    source_kind: str
    source_label: str
    order_index: int
    line_number: int
    parameters: GcodeToolParameters = None


@dataclass(frozen=True)
class GcodeToolRow:
    color_index: int
    path_index: int
    tool_id: str
    bit_label: str
    cut_count: int
    retract_count: int


@dataclass(frozen=True)
class GcodeToolSection:
    source_label: str
    rows: tuple[GcodeToolRow, ...]


@dataclass(frozen=True)
class GcodeToolReportResult:
    path: Path
    sections: tuple[GcodeToolSection, ...]

    @property
    def summary(self) -> str:
        return f"Tool report: wrote {self.path.name}."


@dataclass(frozen=True)
class GcodeBounds:
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


@dataclass(frozen=True)
class GcodeTrace:
    segments: list[GcodeSegment]
    warnings: list[str]
    instruments: list[GcodeInstrument] = None
    sources: list[GcodeSource] = None

    def __post_init__(self):
        instruments = self.instruments or []
        known_instrument_ids = {instrument.id for instrument in instruments}
        missing_segments = [
            segment
            for segment in self.segments
            if segment.instrument_id not in known_instrument_ids
        ]
        if missing_segments or self.instruments is None:
            object.__setattr__(
                self,
                "instruments",
                [*instruments, *_implicit_instruments(missing_segments)],
            )
        if self.sources is None:
            object.__setattr__(self, "sources", _implicit_sources(self.segments))

    @property
    def cut_count(self) -> int:
        return sum(1 for segment in self.segments if segment.movement == GcodeMovementKind.CUT)

    @property
    def retract_count(self) -> int:
        return sum(1 for segment in self.segments if segment.movement == GcodeMovementKind.RETRACT)

    @property
    def tools(self) -> tuple[str, ...]:
        return tuple(sorted({segment.tool_id for segment in self.segments}))

    @property
    def bounds(self) -> GcodeBounds:
        points = [point for segment in self.segments for point in (segment.start, segment.end)]
        return GcodeBounds(
            min(point.x_mm for point in points),
            min(point.y_mm for point in points),
            max(point.x_mm for point in points),
            max(point.y_mm for point in points),
        )

    def filtered(self, source_kinds: set[str]) -> "GcodeTrace":
        segments = [segment for segment in self.segments if segment.source_kind in source_kinds]
        instrument_ids = {segment.instrument_id for segment in segments}
        instruments = [item for item in self.instruments if item.id in instrument_ids]
        sources = [source for source in self.sources if source.kind in source_kinds]
        return GcodeTrace(segments, self.warnings, instruments, sources)

    @property
    def active_instruments(self) -> tuple[GcodeInstrument, ...]:
        instrument_ids = {segment.instrument_id for segment in self.segments}
        return tuple(item for item in self.instruments if item.id in instrument_ids)

    def instrument_counts(self, instrument_id: str) -> tuple[int, int]:
        segments = [segment for segment in self.segments if segment.instrument_id == instrument_id]
        cut_count = sum(1 for segment in segments if segment.movement == GcodeMovementKind.CUT)
        retract_count = sum(
            1 for segment in segments if segment.movement == GcodeMovementKind.RETRACT
        )
        return cut_count, retract_count

    @property
    def active_tool_paths(self) -> tuple[GcodeToolPath, ...]:
        tool_paths: list[GcodeToolPath] = []
        seen_ids: set[str] = set()
        for segment in self.segments:
            id = gcode_tool_path_id(segment.source_kind, segment.tool_id)
            if id in seen_ids:
                continue
            seen_ids.add(id)
            tool_paths.append(
                GcodeToolPath(
                    id=id,
                    tool_id=segment.tool_id,
                    source_kind=segment.source_kind,
                    source_label=segment.source_label or segment.source_kind,
                    order_index=len(tool_paths),
                    line_number=segment.line_number,
                    parameters=self.tool_path_parameters(id),
                )
            )
        return tuple(tool_paths)

    def tool_path_counts(self, tool_path_id: str) -> tuple[int, int]:
        segments = [
            segment
            for segment in self.segments
            if gcode_tool_path_id(segment.source_kind, segment.tool_id) == tool_path_id
        ]
        cut_count = sum(1 for segment in segments if segment.movement == GcodeMovementKind.CUT)
        retract_count = sum(
            1 for segment in segments if segment.movement == GcodeMovementKind.RETRACT
        )
        return cut_count, retract_count

    def tool_path_parameters(self, tool_path_id: str) -> GcodeToolParameters:
        instrument_ids = {
            segment.instrument_id
            for segment in self.segments
            if gcode_tool_path_id(segment.source_kind, segment.tool_id) == tool_path_id
        }
        parameters = {
            instrument.parameters
            for instrument in self.instruments
            if instrument.id in instrument_ids and instrument.parameters
        }
        if len(parameters) == 1:
            return parameters.pop()
        return None


@dataclass
class InterpreterState:
    position: GcodePoint
    unit: str = UNIT_MM
    absolute: bool = True
    active_movement: int = 0
    active_tool: str = DEFAULT_TOOL_ID
    active_instrument_id: str = IMPLICIT_INSTRUMENT_ID
    source_label: str = ""
    tool_change_count: int = 0
    pending_tool_parameters: GcodeToolParameters = None


class GcodeInterpreter:
    def parse_file(self, path: Path, source_kind: str) -> GcodeTrace:
        try:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as error:
            return GcodeTrace([], [f"Could not read {path.name}: {error}"])
        trace = self.parse(raw_text, source_kind, path.name)
        LOGGER.debug(
            "Parsed %s G-code segment(s) from %r as %s",
            len(trace.segments),
            path,
            source_kind,
        )
        return trace

    def parse(self, text: str, source_kind: str, source_label: str = "") -> GcodeTrace:
        state = InterpreterState(GcodePoint(0, 0, 0))
        state.active_instrument_id = f"{source_kind}-implicit"
        state.source_label = source_label or source_kind
        segments: list[GcodeSegment] = []
        instruments: list[GcodeInstrument] = []
        warnings: list[str] = []
        unsupported_commands: set[str] = set()

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            tool_parameters = _parse_tool_parameters(raw_line)
            if tool_parameters:
                state.pending_tool_parameters = tool_parameters
            line = _normalize_modal_line(raw_line, state.active_movement)
            for parsed_line in parse_gcode_lines(line):
                self._process_line(
                    parsed_line,
                    line_number,
                    source_kind,
                    state,
                    segments,
                    instruments,
                    unsupported_commands,
                )
        warnings.extend(
            f"Ignored unsupported command {command}." for command in sorted(unsupported_commands)
        )
        return GcodeTrace(
            segments,
            warnings,
            instruments or None,
            [GcodeSource(source_kind, source_label or source_kind)],
        )

    def _process_line(
        self,
        line: GcodeLine,
        line_number: int,
        source_kind: str,
        state: InterpreterState,
        segments: list[GcodeSegment],
        instruments: list[GcodeInstrument],
        unsupported_commands: set[str],
    ):
        command_letter, command_number = line.command
        if command_letter == "G":
            self._process_g_code(
                command_number,
                line,
                line_number,
                source_kind,
                state,
                segments,
                instruments,
                unsupported_commands,
            )
        elif command_letter == "T" and command_number is not None:
            state.active_tool = str(command_number)
        elif command_letter == "M":
            if command_number == 6:
                self._change_instrument(line, line_number, source_kind, state, instruments)
            elif command_number not in SUPPORTED_M_CODES:
                unsupported_commands.add(f"M{command_number}")

    def _process_g_code(
        self,
        command_number: int,
        line: GcodeLine,
        line_number: int,
        source_kind: str,
        state: InterpreterState,
        segments: list[GcodeSegment],
        instruments: list[GcodeInstrument],
        unsupported_commands: set[str],
    ):
        if command_number not in SUPPORTED_G_CODES:
            unsupported_commands.add(f"G{command_number}")
            return
        if command_number == 20:
            state.unit = UNIT_INCH
            return
        if command_number == 21:
            state.unit = UNIT_MM
            return
        if command_number == 90:
            state.absolute = True
            return
        if command_number == 91:
            state.absolute = False
            return
        if command_number in MOVEMENT_COMMANDS:
            state.active_movement = command_number
            self._move(line, line_number, source_kind, state, segments)

    def _change_instrument(
        self,
        line: GcodeLine,
        line_number: int,
        source_kind: str,
        state: InterpreterState,
        instruments: list[GcodeInstrument],
    ):
        tool_param = line.params.get("T")
        if tool_param is not None:
            state.active_tool = _format_tool_id(tool_param)
        state.tool_change_count += 1
        instrument_id = f"{source_kind}-{state.tool_change_count}"
        instruments.append(
            GcodeInstrument(
                id=instrument_id,
                tool_id=state.active_tool,
                source_kind=source_kind,
                change_index=state.tool_change_count,
                line_number=line_number,
                parameters=state.pending_tool_parameters,
            )
        )
        state.pending_tool_parameters = None
        state.active_instrument_id = instrument_id

    def _move(
        self,
        line: GcodeLine,
        line_number: int,
        source_kind: str,
        state: InterpreterState,
        segments: list[GcodeSegment],
    ):
        next_position = _next_position(state, line.params)
        if next_position == state.position:
            return
        movement = _movement_kind(state.position, next_position)
        segments.append(
            GcodeSegment(
                start=state.position,
                end=next_position,
                movement=movement,
                tool_id=state.active_tool,
                source_kind=source_kind,
                line_number=line_number,
                instrument_id=state.active_instrument_id,
                source_label=state.source_label,
            )
        )
        state.position = next_position


def load_gcode_trace(
    values: dict[str, str],
    base_dir: Path,
    source_kinds: set[str] = None,
) -> GcodeTrace:
    interpreter = GcodeInterpreter()
    segments: list[GcodeSegment] = []
    instruments: list[GcodeInstrument] = []
    sources: list[GcodeSource] = []
    warnings: list[str] = []
    for source_kind, option_key in OUTPUT_OPTIONS:
        if source_kinds and source_kind not in source_kinds:
            continue
        path = _output_path(values, option_key, base_dir)
        if not path.exists():
            warnings.append(f"Missing {source_kind} NC file: {path}")
            continue
        trace = interpreter.parse_file(path, source_kind)
        segments.extend(trace.segments)
        instruments.extend(trace.instruments)
        sources.extend(trace.sources)
        warnings.extend(trace.warnings)
    return GcodeTrace(segments, warnings, instruments, sources)


def generated_output_paths(
    values: dict[str, str],
    base_dir: Path,
    source_kinds: set[str] = None,
) -> tuple[Path, ...]:
    return tuple(
        _output_path(values, option_key, base_dir)
        for source_kind, option_key in OUTPUT_OPTIONS
        if source_kinds is None or source_kind in source_kinds
    )


def gcode_trace_summary(trace: GcodeTrace) -> str:
    tools = ", ".join(trace.tools) if trace.tools else "none"
    return (
        f"G-code: {len(trace.segments)} segment(s), "
        f"{trace.cut_count} cut, {trace.retract_count} retract, tools: {tools}."
    )


def gcode_cutoff_bounds(
    trace: GcodeTrace,
    transform: Callable[[GcodePoint], tuple[float, float]] = None,
) -> GcodeBounds | None:
    points = [_gcode_cutoff_point(point, transform) for point in _gcode_cutoff_points(trace)]
    if not points:
        return None
    return GcodeBounds(
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _gcode_cutoff_points(trace: GcodeTrace) -> list[GcodePoint]:
    return [
        point
        for segment in trace.segments
        if segment.source_kind == "outline" and segment.movement == GcodeMovementKind.CUT
        for point in (segment.start, segment.end)
    ]


def _gcode_cutoff_point(
    point: GcodePoint,
    transform: Callable[[GcodePoint], tuple[float, float]] = None,
) -> tuple[float, float]:
    if transform:
        return transform(point)
    return point.x_mm, point.y_mm


def gcode_cutoff_bounds_summary(
    trace: GcodeTrace,
    transform: Callable[[GcodePoint], tuple[float, float]] = None,
) -> str:
    bounds = gcode_cutoff_bounds(trace, transform)
    if not bounds:
        return ""
    return (
        "Cutoff bounds: "
        f"LB ({_format_mm(bounds.min_x)}, {_format_mm(bounds.min_y)}), "
        f"TR ({_format_mm(bounds.max_x)}, {_format_mm(bounds.max_y)}), "
        f"W {_format_mm(bounds.width)}, H {_format_mm(bounds.height)} mm."
    )


def gcode_instrument_color(index: int) -> str:
    return GCODE_INSTRUMENT_COLORS[index % len(GCODE_INSTRUMENT_COLORS)]


def gcode_tool_parameters_label(trace: GcodeTrace, tool_path_id: str) -> str:
    instrument_ids = {
        segment.instrument_id
        for segment in trace.segments
        if gcode_tool_path_id(segment.source_kind, segment.tool_id) == tool_path_id
    }
    parameters = {
        instrument.parameters
        for instrument in trace.instruments
        if instrument.id in instrument_ids and instrument.parameters
    }
    if not parameters:
        return "-"
    if len(parameters) > 1:
        return "mixed"
    item = parameters.pop()
    return f"{item.tool_type} {item.diameter}"


def gcode_tool_sections(trace: GcodeTrace) -> tuple[GcodeToolSection, ...]:
    rows_by_source: dict[str, list[GcodeToolRow]] = {}
    for color_index, tool_path in enumerate(trace.active_tool_paths):
        cut_count, retract_count = trace.tool_path_counts(tool_path.id)
        if cut_count == 0:
            continue
        rows = rows_by_source.setdefault(tool_path.source_label, [])
        rows.append(
            GcodeToolRow(
                color_index=color_index,
                path_index=len(rows) + 1,
                tool_id=tool_path.tool_id,
                bit_label=gcode_tool_parameters_label(trace, tool_path.id),
                cut_count=cut_count,
                retract_count=retract_count,
            )
        )
    return tuple(
        GcodeToolSection(source_label=source_label, rows=tuple(rows))
        for source_label, rows in rows_by_source.items()
    )


def write_gcode_tool_report(
    values: dict[str, str],
    base_dir: Path,
    source_kinds: set[str] = None,
) -> GcodeToolReportResult:
    trace = load_gcode_trace(values, base_dir, source_kinds)
    sections = gcode_tool_sections(trace)
    output_dir = _output_directory(values, base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / TOOLS_REPORT_NAME
    path.write_text(_format_gcode_tool_report(sections), encoding="utf-8")
    LOGGER.debug("Wrote G-code tool report to %r", path)
    return GcodeToolReportResult(path=path, sections=sections)


def _format_gcode_tool_report(sections: tuple[GcodeToolSection, ...]) -> str:
    lines = ["# NC Tools", ""]
    if not sections:
        lines.append("No cutting tools found.")
        lines.append("")
        return "\n".join(lines)

    for section in sections:
        lines.extend(
            [
                f"## {section.source_label}",
                "",
                "| Path | Tool | Bit | Cut | Pass |",
                "| ---: | --- | --- | ---: | ---: |",
            ]
        )
        for row in section.rows:
            lines.append(
                "| "
                f"{row.path_index} | "
                f"{_escape_markdown_table(row.tool_id)} | "
                f"{_escape_markdown_table(row.bit_label)} | "
                f"{row.cut_count} | "
                f"{row.retract_count} |"
            )
        lines.append("")
    return "\n".join(lines)


def _escape_markdown_table(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def _movement_kind(start: GcodePoint, end: GcodePoint) -> GcodeMovementKind:
    if start.z_mm < 0 or end.z_mm < 0:
        return GcodeMovementKind.CUT
    return GcodeMovementKind.RETRACT


def _normalize_modal_line(raw_line: str, active_movement: int) -> str:
    if COORDINATE_ONLY_RE.match(raw_line):
        return f"G{active_movement} {raw_line}"
    return raw_line


def _format_tool_id(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _parse_tool_parameters(raw_line: str) -> GcodeToolParameters | None:
    match = TOOL_PARAMETER_RE.search(raw_line)
    if not match:
        return None
    return GcodeToolParameters(
        tool_type=match.group("tool_type").lower(),
        diameter=_normalize_diameter(match.group("diameter")),
    )


def _normalize_diameter(value: str) -> str:
    compact_value = re.sub(r"\s+", "", value).lower()
    match = DIAMETER_RE.fullmatch(compact_value)
    if not match:
        return compact_value
    number = match.group("number")
    unit = match.group("unit")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return f"{number}{unit}"


def _format_mm(value: float) -> str:
    formatted = f"{value:.5f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _implicit_instruments(segments: list[GcodeSegment]) -> list[GcodeInstrument]:
    source_by_instrument = {segment.instrument_id: segment.source_kind for segment in segments}
    return [
        _implicit_instrument(instrument_id, source_kind)
        for instrument_id, source_kind in sorted(source_by_instrument.items())
    ]


def _implicit_instrument(instrument_id: str, source_kind: str) -> GcodeInstrument:
    return GcodeInstrument(
        id=instrument_id,
        tool_id=DEFAULT_TOOL_ID,
        source_kind=source_kind,
        change_index=0,
        line_number=0,
    )


def _implicit_sources(segments: list[GcodeSegment]) -> list[GcodeSource]:
    sources: list[GcodeSource] = []
    seen_kinds: set[str] = set()
    for segment in segments:
        if segment.source_kind in seen_kinds:
            continue
        seen_kinds.add(segment.source_kind)
        sources.append(
            GcodeSource(segment.source_kind, segment.source_label or segment.source_kind)
        )
    return sources


def gcode_tool_path_id(source_kind: str, tool_id: str) -> str:
    return f"{source_kind}:{tool_id}"


def _next_position(state: InterpreterState, params: dict[str, float]) -> GcodePoint:
    x_value = _axis_value("X", state.position.x_mm, params, state)
    y_value = _axis_value("Y", state.position.y_mm, params, state)
    z_value = _axis_value("Z", state.position.z_mm, params, state)
    return GcodePoint(x_value, y_value, z_value)


def _axis_value(
    axis: str,
    current_value: float,
    params: dict[str, float],
    state: InterpreterState,
) -> float:
    if axis not in params:
        return current_value
    value = _unit_to_mm(float(params[axis]), state.unit)
    if state.absolute:
        return value
    return current_value + value


def _output_path(values: dict[str, str], option_key: str, base_dir: Path) -> Path:
    output_dir = _output_directory(values, base_dir)
    file_name = values.get(option_key, "").strip()
    if not file_name:
        file_name = _default_output_name(option_key)
    return _resolve_path(file_name, output_dir)


def _output_directory(values: dict[str, str], base_dir: Path) -> Path:
    output_value = values.get("output-dir", "").strip()
    return (
        _resolve_path(output_value, base_dir)
        if output_value
        else _default_output_directory(values, base_dir)
    )


def _default_output_directory(values: dict[str, str], base_dir: Path) -> Path:
    for key in ("front", "back", "drill", "outline"):
        value = values.get(key, "").strip()
        if value:
            return _resolve_path(value, base_dir).parent / "nc"
    return default_output_directory(values)


def _default_output_name(option_key: str) -> str:
    defaults = {
        "front-output": "front.ngc",
        "back-output": "back.ngc",
        "drill-output": "drill.ngc",
        "pre-align-drill-output": "align-drill.ngc",
        "milldrill-output": "milldrill.ngc",
        "outline-output": "outline.ngc",
    }
    return defaults[option_key]


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(os.path.expanduser(value))
    if path.is_absolute():
        return path
    return base_dir / path


def _unit_to_mm(value: float, unit: str) -> float:
    if unit == UNIT_INCH:
        return value * INCH_TO_MM
    return value
