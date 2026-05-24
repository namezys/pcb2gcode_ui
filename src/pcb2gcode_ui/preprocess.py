import logging
from dataclasses import dataclass
from pathlib import Path

from pcb2gcode_ui.gcode_preview import GcodeBounds
from pcb2gcode_ui.options import bool_value, default_values

LOGGER = logging.getLogger(__name__)
PRE_ALIGN_DRILLS_KEY = "pre-align-drills"
PRE_ALIGN_DRILL_DIAMETER_KEY = "pre-align-drill-diameter"
PRE_ALIGN_DRILL_DEPTH_KEY = "pre-align-drill-depth"
PRE_ALIGN_DRILL_OUTPUT_KEY = "pre-align-drill-output"
PRE_ALIGN_DRILL_SOURCE_KEY = "pre-align-drill-source"
ALIGN_DRILL_OUTPUT_DEFAULT = "align-drill.ngc"
ALIGN_DRILL_SOURCE_NAME = "pcb2gcode-ui-align-drills.drl"
UNIT_MM = "mm"
UNIT_INCH = "inch"
INCH_TO_MM = 25.4
ALIGN_DRILL_PASSTHROUGH_KEYS = (
    "ignore-warnings",
    "metric",
    "metricoutput",
    "output-dir",
    "sanity-checks",
    "single-thread",
    "zsafe",
    "spinup-time",
    "spindown-time",
    "zchange",
    "zchange-absolute",
    "nog64",
    "nog91-1",
    "nog81",
    "nom6",
    "drill-feed",
    "drill-speed",
    "x-offset",
    "y-offset",
)


@dataclass(frozen=True)
class PreProcessResult:
    values: dict[str, str]
    processed_files: int
    output_files: tuple[Path, ...]

    @property
    def summary(self) -> str:
        if not self.processed_files:
            return "Pre-process: no files changed."
        files = ", ".join(path.name for path in self.output_files)
        return f"Pre-process: wrote {self.processed_files} file(s): {files}."


@dataclass(frozen=True)
class AlignDrillsPlan:
    x_offset: str
    y_offset: str
    holes: tuple[tuple[float, float], ...]


def pre_process_input_files(
    values: dict[str, str],
    base_dir: Path,
    output_dir: Path,
    align_drills_plan: AlignDrillsPlan = None,
) -> PreProcessResult:
    command_values = dict(values)
    if (
        not _enabled(values, PRE_ALIGN_DRILLS_KEY)
        or not values.get("outline", "").strip()
        or not align_drills_plan
    ):
        return PreProcessResult(command_values, 0, ())

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _alignment_drill_source_path(output_dir)
    processed_content = _alignment_drill_source_content(values, align_drills_plan.holes)
    output_path.write_text(processed_content, encoding="utf-8")
    command_values[PRE_ALIGN_DRILL_SOURCE_KEY] = str(output_path)
    command_values["x-offset"] = align_drills_plan.x_offset
    command_values["y-offset"] = align_drills_plan.y_offset
    LOGGER.debug("Pre-processed alignment drill source into %r", output_path)
    return PreProcessResult(command_values, 1, (output_path,))


def align_drill_generation_values(values: dict[str, str]) -> dict[str, str]:
    command_values = default_values()
    for key in ALIGN_DRILL_PASSTHROUGH_KEYS:
        command_values[key] = values.get(key, command_values.get(key, ""))
    command_values.update(
        {
            "drill": values.get(PRE_ALIGN_DRILL_SOURCE_KEY, ""),
            "drill-output": values.get(PRE_ALIGN_DRILL_OUTPUT_KEY, "")
            or ALIGN_DRILL_OUTPUT_DEFAULT,
            "zdrill": _drill_depth_z_value(values.get(PRE_ALIGN_DRILL_DEPTH_KEY, "")),
            "drill-side": "front",
            "drills-available": values.get(PRE_ALIGN_DRILL_DIAMETER_KEY, ""),
            "onedrill": "true",
        }
    )
    return command_values


def align_drills_plan(values: dict[str, str], cutoff_bounds: GcodeBounds) -> AlignDrillsPlan:
    metric = _enabled(values, "metric")
    front_bounds = _front_side_cutoff_bounds(values, cutoff_bounds)
    center_x = (front_bounds.min_x + front_bounds.max_x) / 2
    center_y = (front_bounds.min_y + front_bounds.max_y) / 2
    x_offset = -center_x
    y_offset = -center_y
    diameter = _diameter_to_mm(values[PRE_ALIGN_DRILL_DIAMETER_KEY], metric)
    if _enabled(values, "mirror-yaxis"):
        mirror_line = "horizontal Y=0"
        holes = (
            (front_bounds.min_x - diameter, center_y),
            (front_bounds.max_x + diameter, center_y),
        )
    else:
        mirror_line = "vertical X=0"
        holes = (
            (center_x, front_bounds.min_y - diameter),
            (center_x, front_bounds.max_y + diameter),
        )
    plan = AlignDrillsPlan(
        x_offset=f"{_format_decimal(x_offset)}mm",
        y_offset=f"{_format_decimal(y_offset)}mm",
        holes=holes,
    )
    LOGGER.debug(
        "Align-drills cutoff bounds: min=(%s, %s), max=(%s, %s), size=(%s, %s)",
        cutoff_bounds.min_x,
        cutoff_bounds.min_y,
        cutoff_bounds.max_x,
        cutoff_bounds.max_y,
        cutoff_bounds.width,
        cutoff_bounds.height,
    )
    LOGGER.debug(
        "Align-drills front-side cutoff bounds: min=(%s, %s), max=(%s, %s), size=(%s, %s)",
        front_bounds.min_x,
        front_bounds.min_y,
        front_bounds.max_x,
        front_bounds.max_y,
        front_bounds.width,
        front_bounds.height,
    )
    LOGGER.debug("Align-drills mirror line: %s", mirror_line)
    LOGGER.debug(
        "Align-drills calculated offsets: x-offset=%s, y-offset=%s",
        plan.x_offset,
        plan.y_offset,
    )
    for idx, hole in enumerate(plan.holes, start=1):
        LOGGER.debug("Align-drills drill point #%s: x=%s, y=%s", idx, hole[0], hole[1])
    return plan


def _front_side_cutoff_bounds(values: dict[str, str], cutoff_bounds: GcodeBounds) -> GcodeBounds:
    if values.get("cut-side", "").strip().lower() != "back":
        return cutoff_bounds
    points = [
        _front_side_cutoff_point(values, cutoff_bounds.min_x, cutoff_bounds.min_y),
        _front_side_cutoff_point(values, cutoff_bounds.min_x, cutoff_bounds.max_y),
        _front_side_cutoff_point(values, cutoff_bounds.max_x, cutoff_bounds.min_y),
        _front_side_cutoff_point(values, cutoff_bounds.max_x, cutoff_bounds.max_y),
    ]
    return GcodeBounds(
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _front_side_cutoff_point(
    values: dict[str, str],
    x_value: float,
    y_value: float,
) -> tuple[float, float]:
    if _enabled(values, "mirror-yaxis"):
        return x_value, -y_value
    return -x_value, y_value


def _alignment_drill_source_content(
    values: dict[str, str],
    holes: tuple[tuple[float, float], ...],
) -> str:
    metric = _enabled(values, "metric")
    unit = UNIT_MM if metric else UNIT_INCH
    diameter = _format_tool_diameter(_diameter_for_unit(values, unit))
    lines = [
        "M48",
        "METRIC,TZ" if unit == UNIT_MM else "INCH,TZ",
        f"T01C{diameter}",
        "%",
        "G90",
        "T01",
        *[
            _format_drill_hit(x_value, y_value, values, unit)
            for x_value, y_value in holes
        ],
        "M30",
        "",
    ]
    return "\n".join(lines)


def _diameter_for_unit(values: dict[str, str], unit: str) -> float:
    diameter_mm = _diameter_to_mm(
        values[PRE_ALIGN_DRILL_DIAMETER_KEY],
        metric_input=_enabled(values, "metric"),
    )
    if unit == UNIT_INCH:
        return diameter_mm / INCH_TO_MM
    return diameter_mm


def _diameter_to_mm(value: str, metric_input: bool) -> float:
    normalized = value.strip().lower()
    if normalized.endswith("mm"):
        return float(normalized[:-2])
    if normalized.endswith("in"):
        return float(normalized[:-2]) * INCH_TO_MM
    diameter = float(normalized)
    if metric_input:
        return diameter
    return diameter * INCH_TO_MM


def _coordinate_for_unit(value_mm: float, unit: str) -> float:
    if unit == UNIT_INCH:
        return value_mm / INCH_TO_MM
    return value_mm


def _format_drill_hit(
    x_value: float,
    y_value: float,
    values: dict[str, str],
    unit: str,
) -> str:
    x_drill = _coordinate_for_unit(x_value, unit)
    y_drill = _coordinate_for_unit(y_value, unit)
    return f"X{_format_decimal(x_drill)}Y{_format_decimal(y_drill)}"


def _format_decimal(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _format_tool_diameter(value: float) -> str:
    return f"{value:.3f}"


def _alignment_drill_source_path(output_dir: Path) -> Path:
    return output_dir / ALIGN_DRILL_SOURCE_NAME


def _drill_depth_z_value(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized.startswith("-"):
        return normalized
    return f"-{normalized.removeprefix('+')}"


def _enabled(values: dict[str, str], key: str) -> bool:
    try:
        return bool_value(values.get(key, "false"))
    except ValueError:
        return False
