from pathlib import Path

from pcb2gcode_ui.gcode_preview import (
    GcodeInstrument,
    GcodeInterpreter,
    GcodeMovementKind,
    GcodeSource,
    GcodeToolParameters,
    GcodeToolPath,
    GcodeTrace,
    gcode_tool_parameters_label,
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
        GcodeToolPath("front:2", "2", "front", "front", 0, 2),
        GcodeToolPath("front:7", "7", "front", "front", 1, 6),
    )


def test_interpreter_reads_tool_parameters_from_comment_before_m6():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "(MSG, Change tool bit to mill diameter 0.50000mm)",
                "T2 M6",
                "G1 X1 Z-0.1",
            ]
        ),
        "front",
    )

    expected_parameters = GcodeToolParameters("mill", "0.5mm")
    assert trace.instruments == [
        GcodeInstrument("front-1", "2", "front", 1, 2, expected_parameters)
    ]
    assert trace.active_tool_paths == (
        GcodeToolPath("front:2", "2", "front", "front", 0, 3, expected_parameters),
    )
    assert gcode_tool_parameters_label(trace, "front:2") == "mill 0.5mm"


def test_interpreter_reads_tool_parameters_from_same_line_comment():
    trace = GcodeInterpreter().parse(
        "T4 M6 (MSG, Change tool bit to DRILL diameter 1.00000mm)\nG1 X1 Z-0.1\n",
        "drill",
    )

    expected_parameters = GcodeToolParameters("drill", "1mm")
    assert trace.instruments == [
        GcodeInstrument("drill-1", "4", "drill", 1, 1, expected_parameters)
    ]
    assert gcode_tool_parameters_label(trace, "drill:4") == "drill 1mm"


def test_interpreter_reads_drill_size_tool_parameter_comment_before_m6():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "G00 Z15.00000 (Retract)",
                "T3",
                "M5      (Spindle stop.)",
                "G04 P1.00000",
                "(MSG, Change tool bit to drill size 0.66mm)",
                "M6      (Tool change.)",
                "M0      (Temporary machine stop.)",
                "M3      (Spindle on clockwise.)",
                "G0 Z2.00000",
                "G04 P1.00000",
                "G1 X1 Z-0.1",
            ]
        ),
        "drill",
    )

    expected_parameters = GcodeToolParameters("drill", "0.66mm")
    assert GcodeInstrument("drill-1", "3", "drill", 1, 6, expected_parameters) in trace.instruments
    assert gcode_tool_parameters_label(trace, "drill:3") == "drill 0.66mm"


def test_interpreter_consumes_tool_parameters_once():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "(MSG, Change tool bit to mill diameter 0.0500in)",
                "T2 M6",
                "G1 X1 Z-0.1",
                "T3 M6",
                "G1 X2",
            ]
        ),
        "front",
    )

    assert trace.instruments[0].parameters == GcodeToolParameters("mill", "0.05in")
    assert trace.instruments[1].parameters is None
    assert gcode_tool_parameters_label(trace, "front:2") == "mill 0.05in"
    assert gcode_tool_parameters_label(trace, "front:3") == "-"


def test_interpreter_ignores_unmatched_tool_parameter_comment():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "(MSG, Change tool bit now)",
                "T2 M6",
                "G1 X1 Z-0.1",
            ]
        ),
        "front",
    )

    assert trace.instruments[0].parameters is None
    assert gcode_tool_parameters_label(trace, "front:2") == "-"


def test_tool_parameter_label_is_mixed_for_grouped_tool_path():
    trace = GcodeInterpreter().parse(
        "\n".join(
            [
                "(MSG, Change tool bit to mill diameter 0.50000mm)",
                "T2 M6",
                "G1 X1 Z-0.1",
                "(MSG, Change tool bit to mill diameter 0.30000mm)",
                "T2 M6",
                "G1 X2",
            ]
        ),
        "front",
    )

    assert gcode_tool_parameters_label(trace, "front:2") == "mixed"


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
        GcodeToolPath("front:none", "none", "front", "front", 0, 2),
        GcodeToolPath("front:4", "4", "front", "front", 1, 4),
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


def test_interpreter_records_source_for_empty_file():
    trace = GcodeInterpreter().parse("", "front", "front.nc")

    assert trace.segments == []
    assert trace.sources == [GcodeSource("front", "front.nc")]


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
    assert {segment.source_label for segment in trace.segments} == {"front.nc"}
    assert trace.active_tool_paths == (GcodeToolPath("front:3", "3", "front", "front.nc", 0, 3),)
    assert trace.sources == [GcodeSource("front", "front.nc")]
    assert trace.instruments == [GcodeInstrument("front-1", "3", "front", 1, 2)]
    assert any("Missing back NC file" in warning for warning in trace.warnings)


def test_trace_filter_keeps_requested_source_only():
    trace = GcodeInterpreter().parse("G21\nG1 X1 Z-0.1\n", "front")
    other = GcodeInterpreter().parse("G21\nG1 X2 Z-0.1\n", "back")
    combined = GcodeTrace(
        [*trace.segments, *other.segments],
        [],
        [*trace.instruments, *other.instruments],
        [*trace.sources, *other.sources],
    )

    filtered = combined.filtered({"back"})

    assert len(filtered.segments) == 1
    assert filtered.segments[0].source_kind == "back"
    assert filtered.sources == other.sources
    assert filtered.active_instruments == tuple(other.instruments)
