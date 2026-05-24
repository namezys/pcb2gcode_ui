from pathlib import Path

from pcb2gcode_ui.preprocess import pre_process_input_files

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


def test_pre_process_align_drills_adds_free_tool_and_origin_drill(
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
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5mm",
        },
        tmp_path,
        tmp_path / "nc",
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
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "0.5",
        },
        tmp_path,
        tmp_path / "nc",
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
            "metric": "true",
            "pre-align-drills": "true",
            "pre-align-drill-diameter": "1mm",
        },
        tmp_path,
        tmp_path / "nc",
    )

    output_path = Path(result.values["drill"])
    data_regression.check({"content": output_path.read_text(encoding="utf-8")})
