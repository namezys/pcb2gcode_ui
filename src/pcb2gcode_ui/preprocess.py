import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

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


def pre_process_input_files(
    values: dict[str, str],
    base_dir: Path,
    output_dir: Path,
) -> PreProcessResult:
    command_values = dict(values)
    if not _enabled(values, PRE_ALIGN_DRILLS_KEY) or not values.get("drill", "").strip():
        return PreProcessResult(command_values, 0, ())

    source_path = _resolve_path(values["drill"], base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = _processed_drill_path(source_path, output_dir)
    content = source_path.read_text(encoding="utf-8", errors="ignore")
    processed_content = _add_alignment_drill(content, values)
    output_path.write_text(processed_content, encoding="utf-8")
    command_values["drill"] = str(output_path)
    LOGGER.debug("Pre-processed drill file %r into %r", source_path, output_path)
    return PreProcessResult(command_values, 1, (output_path,))


def _add_alignment_drill(content: str, values: dict[str, str]) -> str:
    had_trailing_newline = content.endswith("\n")
    lines = content.splitlines()
    unit = _drill_unit(lines)
    diameter = _format_decimal(_diameter_for_unit(values, unit))
    tool_id = _free_tool_id(lines)
    tool_definition = f"T{tool_id}C{diameter}"
    drill_commands = [f"T{tool_id}", "X0Y0"]
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
