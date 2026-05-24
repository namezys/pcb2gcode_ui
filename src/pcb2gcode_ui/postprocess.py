import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pcb2gcode_ui.gcode_preview import generated_output_paths
from pcb2gcode_ui.options import bool_value

LOGGER = logging.getLogger(__name__)
REMOVE_TOOL_SELECT_RE = re.compile(r"T\d+")
SPINDLE_START_RE = re.compile(r"^\s*M0?3\b", re.IGNORECASE)
POST_REMOVE_T_KEY = "post-remove-t"
POST_ORIGIN_BEFORE_M3_KEY = "post-origin-before-m3"
POST_PROCESS_COMMENT_TEMPLATE = "(PP: remove {command})"
ORIGIN_BEFORE_M3_COMMAND = "G00 X0.00000 Y0.00000"


@dataclass(frozen=True)
class PostProcessResult:
    processed_files: int
    changed_files: int
    commented_lines: int
    inserted_origin_moves: int = 0

    @property
    def summary(self) -> str:
        actions: list[str] = []
        if self.commented_lines:
            actions.append(f"commented T* in {self.commented_lines} line(s)")
        if self.inserted_origin_moves:
            actions.append(f"inserted origin move before M3 {self.inserted_origin_moves} time(s)")
        if not actions:
            actions.append("no changes")
        return f"Post-process: changed {self.changed_files} file(s), " + ", ".join(actions) + "."


def post_process_generated_files(values: dict[str, str], base_dir: Path) -> PostProcessResult:
    remove_t_enabled = _enabled(values, POST_REMOVE_T_KEY)
    origin_before_m3_enabled = _enabled(values, POST_ORIGIN_BEFORE_M3_KEY)
    if not remove_t_enabled and not origin_before_m3_enabled:
        return PostProcessResult(0, 0, 0)

    processed_files = 0
    changed_files = 0
    commented_lines = 0
    inserted_origin_moves = 0
    source_kinds = _active_source_kinds(values)
    for path in generated_output_paths(values, base_dir, source_kinds):
        if not path.exists():
            continue
        processed_files += 1
        result = _rewrite_generated_file(path, remove_t_enabled, origin_before_m3_enabled)
        if result.changed:
            changed_files += 1
            commented_lines += result.commented_lines
            inserted_origin_moves += result.inserted_origin_moves
    LOGGER.debug(
        "Post-processed %s generated file(s), changed %s, commented %s line(s), "
        "inserted %s origin move(s)",
        processed_files,
        changed_files,
        commented_lines,
        inserted_origin_moves,
    )
    return PostProcessResult(
        processed_files,
        changed_files,
        commented_lines,
        inserted_origin_moves,
    )


@dataclass(frozen=True)
class RewriteResult:
    commented_lines: int
    inserted_origin_moves: int

    @property
    def changed(self) -> bool:
        return bool(self.commented_lines or self.inserted_origin_moves)


def _rewrite_generated_file(
    path: Path,
    remove_t_enabled: bool,
    origin_before_m3_enabled: bool,
) -> RewriteResult:
    content = path.read_text(encoding="utf-8")
    had_trailing_newline = content.endswith("\n")
    lines = content.splitlines()
    updated_lines: list[str] = []
    commented_lines = 0
    inserted_origin_moves = 0

    for line in lines:
        if origin_before_m3_enabled and _needs_origin_before_m3(updated_lines, line):
            updated_lines.append(ORIGIN_BEFORE_M3_COMMAND)
            inserted_origin_moves += 1
        if remove_t_enabled and REMOVE_TOOL_SELECT_RE.search(line):
            updated_lines.append(_post_process_comment(line))
            commented_lines += 1
        else:
            updated_lines.append(line)

    if not commented_lines and not inserted_origin_moves:
        return RewriteResult(0, 0)

    updated_content = "\n".join(updated_lines)
    if had_trailing_newline and updated_content:
        updated_content += "\n"
    path.write_text(updated_content, encoding="utf-8")
    return RewriteResult(commented_lines, inserted_origin_moves)


def _needs_origin_before_m3(updated_lines: list[str], line: str) -> bool:
    if not SPINDLE_START_RE.search(line):
        return False
    previous_line = _previous_non_empty_line(updated_lines)
    return previous_line != ORIGIN_BEFORE_M3_COMMAND


def _previous_non_empty_line(lines: list[str]) -> str:
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return ""


def _post_process_comment(command: str) -> str:
    return POST_PROCESS_COMMENT_TEMPLATE.format(command=command.strip())


def _enabled(values: dict[str, str], key: str) -> bool:
    try:
        return bool_value(values.get(key, "false"))
    except ValueError:
        return False


def _active_source_kinds(values: dict[str, str]) -> set[str]:
    source_kinds: set[str] = set()
    for source_kind in ("front", "back", "drill", "outline"):
        if values.get(source_kind, "").strip():
            source_kinds.add(source_kind)
    if values.get("drill", "").strip() and _milldrill_enabled(values):
        source_kinds.add("milldrill")
    if values.get("pre-align-drill-source", "").strip():
        source_kinds.add("align-drill")
    return source_kinds


def _milldrill_enabled(values: dict[str, str]) -> bool:
    return any(
        values.get(key, "").strip()
        for key in ("milldrill-diameter", "min-milldrill-hole-diameter", "zmilldrill")
    )
