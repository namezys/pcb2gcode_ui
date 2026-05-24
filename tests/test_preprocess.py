from pathlib import Path

from pcb2gcode_ui.gcode_preview import GcodeBounds
from pcb2gcode_ui.preprocess import (
    ALIGN_DRILL_OUTPUT_DEFAULT,
    PRE_ALIGN_DRILL_SOURCE_KEY,
    align_drill_generation_values,
    align_drills_plan,
    pre_process_input_files,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "preprocess"


def test_pre_process_align_drills_disabled_leaves_values_unchanged(tmp_path: Path):
    drill_path = tmp_path / "basic_metric.drl"
    drill_path.write_text((FIXTURES_DIR / "basic_metric.drl").read_text(), encoding="utf-8")

    result = pre_process_input_files(
        {
            "drill": str(drill_path),
            "pre-align-drills": "false",
            "pre-align-drill-diameter": "0.5mm",
        },
        tmp_path,
        tmp_path / "nc",
    )

    assert result.values["drill"] == str(drill_path)
    assert result.processed_files == 0
    assert result.output_files == ()
    assert not (tmp_path / "nc").exists()


def test_pre_process_align_drills_skips_without_outline(tmp_path: Path):
    drill_path = tmp_path / "basic_metric.drl"
    drill_path.write_text((FIXTURES_DIR / "basic_metric.drl").read_text(), encoding="utf-8")

    result = pre_process_input_files(
        {
            "drill": str(drill_path),
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5mm",
        },
        tmp_path,
        tmp_path / "nc",
    )

    assert result.values["drill"] == str(drill_path)
    assert result.processed_files == 0
    assert result.output_files == ()
    assert not (tmp_path / "nc").exists()


def test_pre_process_align_drills_adds_free_tool_and_two_vertical_drills(
    tmp_path: Path,
    data_regression,
):
    drill_path = tmp_path / "basic_metric.drl"
    drill_path.write_text(
        (FIXTURES_DIR / "basic_metric.drl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = pre_process_input_files(
        {
            "drill": str(drill_path),
            "outline": str(tmp_path / "outline.gbr"),
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5mm",
        },
        tmp_path,
        tmp_path / "nc",
        align_drills_plan(
            {
                "metric": "true",
                "pre-align-drill-diameter": "0.5mm",
            },
            GcodeBounds(10, 20, 30, 40),
        ),
    )

    output_path = Path(result.values[PRE_ALIGN_DRILL_SOURCE_KEY])
    data_regression.check(
        {
            "values_drill": Path(result.values["drill"]).name,
            "values_align_source": output_path.name,
            "processed_files": result.processed_files,
            "output_files": [path.name for path in result.output_files],
            "content": output_path.read_text(encoding="utf-8"),
        }
    )
    assert drill_path.read_text(encoding="utf-8") == (
        FIXTURES_DIR / "basic_metric.drl"
    ).read_text(encoding="utf-8")


def test_pre_process_align_drills_converts_metric_diameter_to_inch_file(
    tmp_path: Path,
    data_regression,
):
    drill_path = tmp_path / "inch_unpadded.drl"
    drill_path.write_text(
        (FIXTURES_DIR / "inch_unpadded.drl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = pre_process_input_files(
        {
            "drill": str(drill_path),
            "outline": str(tmp_path / "outline.gbr"),
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5",
        },
        tmp_path,
        tmp_path / "nc",
        align_drills_plan(
            {
                "metric": "true",
                "pre-align-drill-diameter": "0.5",
            },
            GcodeBounds(10, 20, 30, 40),
        ),
    )

    output_path = Path(result.values[PRE_ALIGN_DRILL_SOURCE_KEY])
    data_regression.check({"content": output_path.read_text(encoding="utf-8")})


def test_pre_process_align_drills_ignores_t0_when_selecting_free_tool(
    tmp_path: Path,
    data_regression,
):
    drill_path = tmp_path / "only_t0.drl"
    drill_path.write_text(
        (FIXTURES_DIR / "only_t0.drl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = pre_process_input_files(
        {
            "drill": str(drill_path),
            "outline": str(tmp_path / "outline.gbr"),
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "1mm",
        },
        tmp_path,
        tmp_path / "nc",
        align_drills_plan(
            {
                "metric": "true",
                "pre-align-drill-diameter": "1mm",
            },
            GcodeBounds(10, 20, 30, 40),
        ),
    )

    output_path = Path(result.values[PRE_ALIGN_DRILL_SOURCE_KEY])
    data_regression.check({"content": output_path.read_text(encoding="utf-8")})


def test_align_drill_generation_values_use_front_drill_only():
    values = {
        "front": "front.gbr",
        "back": "back.gbr",
        "outline": "outline.gbr",
        "drill": "main.drl",
        "drill-output": "drill.ngc",
        "pre-align-drill-source": "align-source.drl",
        "pre-align-drill-output": "align-output.ngc",
        "pre-align-drill-diameter": "0.5mm",
        "pre-align-drill-depth": "1.2mm",
        "drill-side": "back",
        "drills-available": "0.8mm",
        "onedrill": "false",
        "milldrill-diameter": "1mm",
        "min-milldrill-hole-diameter": "1mm",
        "zmilldrill": "-1mm",
        "mill-diameters": "0.5mm,0.1mm",
        "zwork": "-0.01mm",
        "mill-feed": "150",
        "cutter-diameter": "2mm",
        "zcut": "-2.5mm",
        "cut-feed": "80",
        "cut-side": "back",
        "x-offset": "-10mm",
        "y-offset": "-20mm",
    }

    command_values = align_drill_generation_values(values)

    assert command_values["front"] == ""
    assert command_values["back"] == ""
    assert command_values["outline"] == ""
    assert command_values["drill"] == "align-source.drl"
    assert command_values["drill-output"] == "align-output.ngc"
    assert command_values["zdrill"] == "-1.2mm"
    assert command_values["drill-side"] == "front"
    assert command_values["drills-available"] == "0.5mm"
    assert command_values["onedrill"] == "true"
    assert command_values["milldrill-diameter"] == ""
    assert command_values["min-milldrill-hole-diameter"] == ""
    assert command_values["zmilldrill"] == ""
    assert command_values["mill-diameters"] == "0"
    assert command_values["zwork"] == ""
    assert command_values["mill-feed"] == ""
    assert command_values["cutter-diameter"] == ""
    assert command_values["zcut"] == ""
    assert command_values["cut-feed"] == ""
    assert command_values["cut-side"] == "auto"
    assert command_values["x-offset"] == "-10mm"
    assert command_values["y-offset"] == "-20mm"


def test_align_drill_generation_values_use_default_output():
    command_values = align_drill_generation_values(
        {
            "pre-align-drill-source": "align-source.drl",
            "pre-align-drill-diameter": "0.5mm",
            "pre-align-drill-depth": "-1mm",
        }
    )

    assert command_values["drill-output"] == ALIGN_DRILL_OUTPUT_DEFAULT


def test_align_drill_generation_values_keep_negative_depth():
    command_values = align_drill_generation_values(
        {
            "pre-align-drill-source": "align-source.drl",
            "pre-align-drill-diameter": "0.5mm",
            "pre-align-drill-depth": "-1mm",
        }
    )

    assert command_values["zdrill"] == "-1mm"


def test_align_drills_plan_uses_horizontal_mirror_line_with_y_mirror():
    plan = align_drills_plan(
        {
            "metric": "true",
            "mirror-yaxis": "true",
            "pre-align-drill-diameter": "1mm",
        },
        GcodeBounds(10, 20, 30, 40),
    )

    assert plan.x_offset == "-20mm"
    assert plan.y_offset == "-30mm"
    assert plan.holes == ((9, 30), (31, 30))


def test_align_drills_plan_accounts_for_existing_offsets():
    plan = align_drills_plan(
        {
            "metric": "true",
            "x-offset": "5mm",
            "y-offset": "-3mm",
            "pre-align-drill-diameter": "2mm",
        },
        GcodeBounds(15, 17, 35, 37),
    )

    assert plan.x_offset == "-25mm"
    assert plan.y_offset == "-27mm"
    assert plan.holes == ((25, 15), (25, 39))


def test_align_drills_plan_converts_back_cutoff_bounds_to_front_side():
    plan = align_drills_plan(
        {
            "metric": "true",
            "cut-side": "back",
            "pre-align-drill-diameter": "1mm",
        },
        GcodeBounds(-30, 20, -10, 40),
    )

    assert plan.x_offset == "-20mm"
    assert plan.y_offset == "-30mm"
    assert plan.holes == ((20, 19), (20, 41))


def test_align_drills_plan_converts_y_mirrored_back_cutoff_bounds_to_front_side():
    plan = align_drills_plan(
        {
            "metric": "true",
            "cut-side": "back",
            "mirror-yaxis": "true",
            "pre-align-drill-diameter": "1mm",
        },
        GcodeBounds(10, -40, 30, -20),
    )

    assert plan.x_offset == "-20mm"
    assert plan.y_offset == "-30mm"
    assert plan.holes == ((9, 30), (31, 30))
