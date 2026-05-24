import logging
import sys
from pathlib import Path

from pcb2gcode_ui.options import default_output_directory
from pcb2gcode_ui.preprocess import align_drill_generation_values
from pcb2gcode_ui.runner import build_arguments, run_command


def test_default_output_directory_uses_first_input_parent(tmp_path: Path):
    gerber_path = tmp_path / "board-F.Cu.gbr"

    assert default_output_directory({"front": str(gerber_path)}) == tmp_path / "nc"


def test_build_arguments_uses_noconfigfile_and_key_value_flags():
    args = build_arguments(
        {
            "metric": "true",
            "front": "front.gbr",
            "output-dir": "nc",
            "backtrack": "inf",
        }
    )

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


def test_build_arguments_skips_ui_only_process_options():
    args = build_arguments(
        {
            "post-remove-t": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5mm",
            "pre-align-drill-depth": "-1mm",
            "pre-align-drill-output": "align.ngc",
            "pre-align-drill-source": "align.drl",
            "post-origin-before-m3": "true",
        }
    )

    assert args == ["--noconfigfile"]


def test_build_arguments_for_align_drill_run_excludes_milling_and_cutting(tmp_path: Path):
    values = align_drill_generation_values(
        {
            "metric": "true",
            "metricoutput": "true",
            "output-dir": str(tmp_path / "out"),
            "front": "front.gbr",
            "back": "back.gbr",
            "outline": "outline.gbr",
            "drill": "main.drl",
            "zsafe": "2",
            "zchange": "15",
            "nog81": "true",
            "mill-diameters": "0.5mm,0.1mm",
            "zwork": "-0.01mm",
            "mill-feed": "150",
            "cutter-diameter": "2mm",
            "zcut": "-2.5mm",
            "cut-feed": "80",
            "cut-side": "back",
            "x-offset": "-10mm",
            "y-offset": "-20mm",
            "drill-feed": "200",
            "drill-speed": "24000",
            "pre-align-drill-source": str(tmp_path / "align.drl"),
            "pre-align-drill-output": "align.nc",
            "pre-align-drill-depth": "5",
            "pre-align-drill-diameter": "3",
        }
    )

    args = build_arguments(values, base_dir=tmp_path)

    assert args == [
        "--noconfigfile",
        "--metric=true",
        "--metricoutput=true",
        f"--output-dir={tmp_path / 'out'}",
        f"--drill={tmp_path / 'align.drl'}",
        "--zsafe=2",
        "--zchange=15",
        "--nog81=true",
        "--zdrill=-5",
        "--drill-feed=200",
        "--drill-speed=24000",
        "--drill-side=front",
        "--drills-available=3",
        "--onedrill=true",
        "--drill-output=align.nc",
        "--x-offset=-10mm",
        "--y-offset=-20mm",
    ]


def test_run_command_logs_stdout_and_stderr(caplog, tmp_path: Path):
    caplog.set_level(logging.DEBUG, logger="pcb2gcode_ui.runner")

    result = run_command(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "print('stdout text'); "
                "print('stderr text', file=sys.stderr); "
                "raise SystemExit(3)"
            ),
        ],
        tmp_path,
    )

    assert result.return_code == 3
    assert result.output == "stdout text\nstderr text\n"
    assert "Command stdout:\nstdout text" in caplog.text
    assert "Command stderr:\nstderr text" in caplog.text
