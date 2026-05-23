from pathlib import Path

from pcb2gcode_ui.gcode_preview import (
    GcodeInterpreter,
    GcodeMovementKind,
    GcodeTrace,
    load_gcode_trace,
)


def test_interpreter_parses_units_absolute_modal_moves_and_tools():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G21",
                "G90",
                "T2 M6",
                "G0 X1 Y2 Z1",
                "G1 Z-0.1 F100",
                "X3 Y4",
            ]
        ),
        "front",
    )

    assert len(trace.segments) == 3
    assert trace.segments[0].movement == GcodeMovementKind.RETRACT
    assert trace.segments[1].movement == GcodeMovementKind.CUT
    assert trace.segments[2].movement == GcodeMovementKind.CUT
    assert trace.segments[2].end.x_mm == 3
    assert trace.segments[2].end.y_mm == 4
    assert trace.segments[2].tool_id == "2"


def test_interpreter_supports_inch_and_incremental_modes():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G20",
                "G90",
                "G0 X1 Y1 Z0.1",
                "G91",
                "G1 X1 Z-0.2",
            ]
        ),
        "back",
    )

    assert trace.segments[-1].end.x_mm == 50.8
    assert trace.segments[-1].end.z_mm == -2.54
    assert trace.segments[-1].movement == GcodeMovementKind.CUT


def test_interpreter_ignores_unsupported_commands_once():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G2 X1 Y1 I1 J0",
                "G2 X2 Y2 I1 J0",
                "M3 S1000",
                "M3 S1000",
            ]
        ),
        "outline",
    )

    assert trace.segments == []
    assert trace.warnings == [
        "Ignored unsupported command G2.",
        "Ignored unsupported command M3.",
    ]


def test_load_gcode_trace_reads_configured_output_files(tmp_path: Path):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    front_path = output_dir / "front.nc"
    front_path.write_text("G21\nT3 M6\nG0 X0 Y0 Z1\nG1 Z-0.1\nX1\n", encoding="utf-8")

    trace = load_gcode_trace(
        {
            "output-dir": str(output_dir),
            "front-output": "front.nc",
            "back-output": "back.nc",
        },
        tmp_path,
        {"front", "back"},
    )

    assert len(trace.segments) == 3
    assert trace.tools == ("3",)
    assert any("Missing back NC file" in warning for warning in trace.warnings)


def test_trace_filter_keeps_requested_source_only():
    trace = GcodeInterpreter().parse("G21\nG1 X1 Z-0.1\n", "front")
    other = GcodeInterpreter().parse("G21\nG1 X2 Z-0.1\n", "back")
    combined = GcodeTrace([*trace.segments, *other.segments], [])

    filtered = combined.filtered({"back"})

    assert len(filtered.segments) == 1
    assert filtered.segments[0].source_kind == "back"
