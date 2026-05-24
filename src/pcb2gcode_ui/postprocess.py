import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pcb2gcode_ui.gcode_preview import generated_output_paths
from pcb2gcode_ui.options import bool_value

LOGGER = logging.getLogger(__name__)
REMOVE_TOOL_SELECT_RE = re.compile(r"T\d+")
POST_REMOVE_T_KEY = "post-remove-t"
POST_PROCESS_COMMENT_TEMPLATE = "(PP: remove {command})"


@dataclass(frozen=True)
class PostProcessResult:
    processed_files: int
    changed_files: int
    commented_lines: int

    @property
    def summary(self) -> str:
        return (
            "Post-process: commented T* lines in "
            f"{self.changed_files} file(s), {self.commented_lines} line(s)."
        )


def post_process_generated_files(values: dict[str, str], base_dir: Path) -> PostProcessResult:
    if not _enabled(values, POST_REMOVE_T_KEY):
        return PostProcessResult(0, 0, 0)

    processed_files = 0
    changed_files = 0
    commented_lines = 0
    source_kinds = _active_source_kinds(values)
    for path in generated_output_paths(values, base_dir, source_kinds):
        if not path.exists():
            continue
        processed_files += 1
        result = _comment_tool_select_lines(path)
        if result:
            changed_files += 1
            commented_lines += result
    LOGGER.debug(
        "Post-processed %s generated file(s), changed %s, commented %s line(s)",
        processed_files,
        changed_files,
        commented_lines,
    )
    return PostProcessResult(processed_files, changed_files, commented_lines)


def _comment_tool_select_lines(path: Path) -> int:
    content = path.read_text(encoding="utf-8")
    had_trailing_newline = content.endswith("\n")
    lines = content.splitlines()
    updated_lines = [
        _post_process_comment(line) if REMOVE_TOOL_SELECT_RE.search(line) else line
        for line in lines
    ]
    changed_count = sum(1 for line in lines if REMOVE_TOOL_SELECT_RE.search(line))
    if not changed_count:
        return 0

    updated_content = "\n".join(updated_lines)
    if had_trailing_newline and updated_content:
        updated_content += "\n"
    path.write_text(updated_content, encoding="utf-8")
    return changed_count


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
    return source_kinds


def _milldrill_enabled(values: dict[str, str]) -> bool:
    return any(
        values.get(key, "").strip()
        for key in ("milldrill-diameter", "min-milldrill-hole-diameter", "zmilldrill")
    )
