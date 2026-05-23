from pathlib import Path

from pcb2gcode_ui.gcode_preview import (
    GcodeInstrument,
    GcodeInterpreter,
    GcodeMovementKind,
    GcodeToolPath,
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
    assert trace.segments[2].instrument_id == "front-1"
    assert trace.instruments == [GcodeInstrument("front-1", "2", "front", 1, 3)]


def test_interpreter_tracks_m6_but_collects_paths_by_tool():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "T2 M6",
                "G1 X1 Z-0.1",
                "T2 M6",
                "G1 X2",
                "M6 T7",
                "G1 X3",
            ]
        ),
        "front",
    )

    assert [instrument.tool_id for instrument in trace.instruments] == ["2", "2", "7"]
    assert [instrument.change_index for instrument in trace.instruments] == [1, 2, 3]
    assert [segment.instrument_id for segment in trace.segments] == [
        "front-1",
        "front-2",
        "front-3",
    ]
    assert trace.active_tool_paths == (
        GcodeToolPath("front:2", "2", "front", 0, 2),
        GcodeToolPath("front:7", "7", "front", 1, 6),
    )


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


def test_interpreter_treats_any_subzero_segment_endpoint_as_cut():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G21",
                "G0 X0 Y0 Z1",
                "G1 Z-0.1",
                "G1 Z0",
                "G1 X1",
            ]
        ),
        "front",
    )

    assert [segment.movement for segment in trace.segments] == [
        GcodeMovementKind.RETRACT,
        GcodeMovementKind.CUT,
        GcodeMovementKind.CUT,
        GcodeMovementKind.RETRACT,
    ]


def test_interpreter_keeps_initial_path_as_initial_tool():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G21",
                "G0 X0 Y0 Z1",
                "T4 M6",
                "G1 Z-0.1",
            ]
        ),
        "front",
    )

    assert trace.instruments == [
        GcodeInstrument("front-1", "4", "front", 1, 3),
        GcodeInstrument("front-implicit", "none", "front", 0, 0),
    ]
    assert [segment.instrument_id for segment in trace.segments] == [
        "front-implicit",
        "front-1",
    ]
    assert [segment.tool_id for segment in trace.segments] == ["none", "4"]
    assert trace.segments[-1].instrument_id == "front-1"
    assert trace.active_tool_paths == (
        GcodeToolPath("front:none", "none", "front", 0, 2),
        GcodeToolPath("front:4", "4", "front", 1, 4),
    )


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
    assert trace.instruments == [GcodeInstrument("front-1", "3", "front", 1, 2)]
    assert any("Missing back NC file" in warning for warning in trace.warnings)


def test_trace_filter_keeps_requested_source_only():
    trace = GcodeInterpreter().parse("G21\nG1 X1 Z-0.1\n", "front")
    other = GcodeInterpreter().parse("G21\nG1 X2 Z-0.1\n", "back")
    combined = GcodeTrace(
        [*trace.segments, *other.segments],
        [],
        [*trace.instruments, *other.instruments],
    )

    filtered = combined.filtered({"back"})

    assert len(filtered.segments) == 1
    assert filtered.segments[0].source_kind == "back"
    assert filtered.active_instruments == tuple(other.instruments)
