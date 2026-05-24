from pathlib import Path

from pcb2gcode_ui.gcode_preview import GcodeBounds
from pcb2gcode_ui.preprocess import align_drills_plan, pre_process_input_files

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

    output_path = tmp_path / "nc" / "basic_metric.pcb2gcode-ui-align-drills.drl"
    data_regression.check(
        {
            "values_drill": Path(result.values["drill"]).name,
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

    output_path = Path(result.values["drill"])
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

    output_path = Path(result.values["drill"])
    data_regression.check({"content": output_path.read_text(encoding="utf-8")})


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
