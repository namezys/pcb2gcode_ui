from pathlib import Path

from pcb2gcode_ui.postprocess import post_process_generated_files

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "postprocess"


def test_post_process_remove_t_disabled_leaves_files_unchanged(tmp_path: Path, data_regression):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    output_path = output_dir / "front.ngc"
    output_path.write_text(
        (FIXTURES_DIR / "tool_select_front.ngc").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = post_process_generated_files(
        {"output-dir": str(output_dir), "post-remove-t": "false"},
        tmp_path,
    )

    data_regression.check(
        {
            "processed_files": result.processed_files,
            "changed_files": result.changed_files,
            "commented_lines": result.commented_lines,
            "front": output_path.read_text(encoding="utf-8"),
        }
    )


def test_post_process_remove_t_comments_tool_select_lines(tmp_path: Path, data_regression):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    output_path = output_dir / "front.ngc"
    output_path.write_text(
        (FIXTURES_DIR / "tool_select_front.ngc").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = post_process_generated_files(
        {
            "front": str(tmp_path / "front.gbr"),
            "output-dir": str(output_dir),
            "post-remove-t": "true",
        },
        tmp_path,
    )

    data_regression.check(
        {
            "processed_files": result.processed_files,
            "changed_files": result.changed_files,
            "commented_lines": result.commented_lines,
            "front": output_path.read_text(encoding="utf-8"),
        }
    )


def test_post_process_remove_t_skips_missing_outputs(tmp_path: Path, data_regression):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    front_path = output_dir / "front.ngc"
    front_path.write_text(
        (FIXTURES_DIR / "minimal_front.ngc").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = post_process_generated_files(
        {
            "front": str(tmp_path / "front.gbr"),
            "output-dir": str(output_dir),
            "post-remove-t": "true",
        },
        tmp_path,
    )

    data_regression.check(
        {
            "processed_files": result.processed_files,
            "changed_files": result.changed_files,
            "commented_lines": result.commented_lines,
            "front": front_path.read_text(encoding="utf-8"),
        }
    )


def test_post_process_remove_t_skips_stale_inactive_outputs(
    tmp_path: Path,
    data_regression,
):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    front_path = output_dir / "front.ngc"
    back_path = output_dir / "back.ngc"
    source_content = (FIXTURES_DIR / "tool_select_front.ngc").read_text(encoding="utf-8")
    front_path.write_text(source_content, encoding="utf-8")
    back_path.write_text(source_content, encoding="utf-8")

    result = post_process_generated_files(
        {
            "front": str(tmp_path / "front.gbr"),
            "output-dir": str(output_dir),
            "post-remove-t": "true",
        },
        tmp_path,
    )

    data_regression.check(
        {
            "processed_files": result.processed_files,
            "changed_files": result.changed_files,
            "commented_lines": result.commented_lines,
            "front": front_path.read_text(encoding="utf-8"),
            "back": back_path.read_text(encoding="utf-8"),
        }
    )
