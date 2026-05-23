from pathlib import Path

from pcb2gcode_ui.options import default_output_directory
from pcb2gcode_ui.runner import build_arguments


def test_default_output_directory_uses_first_input_parent(tmp_path: Path):
    gerber_path = tmp_path / "board-F.Cu.gbr"

    assert default_output_directory({"front": str(gerber_path)}) == tmp_path / "nc"


def test_build_arguments_uses_noconfigfile_and_key_value_flags():
    args = build_arguments({"metric": "true", "front": "front.gbr", "output-dir": "nc"})

    assert args == [
        "--noconfigfile",
        "--metric=true",
        f"--output-dir={Path.cwd() / 'nc'}",
        f"--front={Path.cwd() / 'front.gbr'}",
    ]


def test_build_arguments_resolves_relative_paths_against_base_dir(tmp_path: Path):
    args = build_arguments({"front": "front.gbr", "output-dir": "nc"}, base_dir=tmp_path)

    assert args == [
        "--noconfigfile",
        f"--output-dir={tmp_path / 'nc'}",
        f"--front={tmp_path / 'front.gbr'}",
    ]
