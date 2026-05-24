import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from pcb2gcode_ui.gcode_preview import GcodeBounds
from pcb2gcode_ui.options import bool_value

LOGGER = logging.getLogger(__name__)
PRE_ALIGN_DRILLS_KEY = "pre-align-drills"
PRE_ALIGN_DRILL_DIAMETER_KEY = "pre-align-drill-diameter"
PROCESSED_DRILL_SUFFIX = ".pcb2gcode-ui-align-drills"
UNIT_MM = "mm"
UNIT_INCH = "inch"
INCH_TO_MM = 25.4
TOOL_RE = re.compile(r"^\s*T(?P<id>\d+)(?:C(?P<diameter>[+-]?\d+(?:\.\d+)?))?\b")
TRAILING_COMMANDS = {"T0", "M30"}


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
        or not values.get("drill", "").strip()
        or not values.get("outline", "").strip()
        or not align_drills_plan
    ):
        return PreProcessResult(command_values, 0, ())

    source_path = _resolve_path(values["drill"], base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _processed_drill_path(source_path, output_dir)
    content = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_content = _add_alignment_drills(content, values, align_drills_plan.holes)
    output_path.write_text(processed_content, encoding="utf-8")
    command_values["drill"] = str(output_path)
    command_values["x-offset"] = align_drills_plan.x_offset
    command_values["y-offset"] = align_drills_plan.y_offset
    LOGGER.debug("Pre-processed drill file %r into %r", source_path, output_path)
    return PreProcessResult(command_values, 1, (output_path,))


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


def _add_alignment_drills(
    content: str,
    values: dict[str, str],
    holes: tuple[tuple[float, float], ...],
) -> str:
    had_trailing_newline = content.endswith("\n")
    lines = content.splitlines()
    unit = _drill_unit(lines)
    diameter = _format_tool_diameter(_diameter_for_unit(values, unit))
    tool_id = _free_tool_id(lines)
    tool_definition = f"T{tool_id}C{diameter}"
    drill_commands = [
        f"T{tool_id}",
        *[
            _format_drill_hit(x_value, y_value, values, unit)
            for x_value, y_value in holes
        ],
    ]
    updated_lines = _insert_tool_definition(lines, tool_definition)
    updated_lines = _insert_drill_commands(updated_lines, drill_commands)
    processed_content = "\n".join(updated_lines)
    if had_trailing_newline and processed_content:
        processed_content += "\n"
    return processed_content


def _drill_unit(lines: list[str]) -> str:
    for raw_line in lines:
        line = raw_line.strip().upper()
        if "METRIC" in line or line == "M71":
            return UNIT_MM
        if "INCH" in line or line == "M72":
            return UNIT_INCH
    return UNIT_INCH


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


def _free_tool_id(lines: list[str]) -> str:
    tool_ids = [
        match.group("id")
        for line in lines
        if (match := TOOL_RE.match(line.strip().upper()))
        and int(match.group("id")) > 0
    ]
    used_tool_numbers = {int(tool_id) for tool_id in tool_ids}
    tool_number = 1
    while tool_number in used_tool_numbers:
        tool_number += 1
    width = max((len(tool_id) for tool_id in tool_ids), default=1)
    return str(tool_number).zfill(width)


def _insert_tool_definition(lines: list[str], tool_definition: str) -> list[str]:
    updated_lines = list(lines)
    for idx, raw_line in enumerate(updated_lines):
        if raw_line.strip() == "%":
            updated_lines.insert(idx, tool_definition)
            return updated_lines

    last_tool_idx = None
    for idx, raw_line in enumerate(updated_lines):
        if TOOL_RE.match(raw_line.strip().upper()):
            last_tool_idx = idx
    insert_idx = last_tool_idx + 1 if last_tool_idx is not None else len(updated_lines)
    updated_lines.insert(insert_idx, tool_definition)
    return updated_lines


def _insert_drill_commands(lines: list[str], drill_commands: list[str]) -> list[str]:
    updated_lines = list(lines)
    body_start = 0
    for idx, raw_line in enumerate(updated_lines):
        if raw_line.strip() == "%":
            body_start = idx + 1
            break
    insert_idx = len(updated_lines)
    for idx in range(len(updated_lines) - 1, body_start - 1, -1):
        if updated_lines[idx].strip().upper() in TRAILING_COMMANDS:
            insert_idx = idx
    updated_lines[insert_idx:insert_idx] = drill_commands
    return updated_lines


def _format_decimal(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _format_tool_diameter(value: float) -> str:
    return f"{value:.3f}"


def _processed_drill_path(source_path: Path, output_dir: Path) -> Path:
    suffix = source_path.suffix or ".drl"
    return output_dir / f"{source_path.stem}{PROCESSED_DRILL_SUFFIX}{suffix}"


def _resolve_path(value: str, base_dir: Path = None) -> Path:
    path = Path(os.path.expanduser(value))
    if path.is_absolute():
        return path
    return (base_dir or Path.cwd()) / path


def _enabled(values: dict[str, str], key: str) -> bool:
    try:
        return bool_value(values.get(key, "false"))
    except ValueError:
        return False
