import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from pcb2gcode_ui.gcode_preview import (
    GcodeInterpreter,
    GcodeTrace,
    gcode_instrument_color,
)
from pcb2gcode_ui.help_content import OPTION_HELP_BY_KEY
from pcb2gcode_ui.millproject import parse_millproject
from pcb2gcode_ui.options import SPEC_BY_KEY
from pcb2gcode_ui.preview import PreviewResult, PreviewSide
from pcb2gcode_ui.ui import Pcb2GCodeApp


@dataclass
class FakePage:
    title: str = ""
    scroll: object = None
    services: list[object] = field(default_factory=list)
    controls: list[object] = field(default_factory=list)
    dialogs: list[object] = field(default_factory=list)

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        if self.dialogs:
            return self.dialogs.pop()
        return None


@dataclass
class FakeFile:
    path: str


@dataclass
class FakeEvent:
    control: object


@dataclass
class FakeSegmentedControl:
    selected: list[PreviewSide]


class FakeFilePicker:
    def __init__(self, selected_files: list[FakeFile] = None):
        self.selected_files = selected_files or []
        self.kwargs: dict[str, object] = {}

    async def pick_files(self, **kwargs) -> list[FakeFile]:
        self.kwargs = kwargs
        return self.selected_files


class FakeDirectoryPicker:
    def __init__(self, selected_path: str = ""):
        self.selected_path = selected_path
        self.kwargs: dict[str, object] = {}

    async def get_directory_path(self, **kwargs) -> str:
        self.kwargs = kwargs
        return self.selected_path


class FakeSavePicker:
    def __init__(self, selected_path: str = ""):
        self.selected_path = selected_path
        self.kwargs: dict[str, object] = {}

    async def save_file(self, **kwargs) -> str:
        self.kwargs = kwargs
        return self.selected_path


class FakePreviewRenderer:
    def __init__(self):
        self.base_dir: Path = None
        self.aux_layer: Path = None
        self.gcode_trace = None
        self.show_gcode = False
        self.show_front = False
        self.show_back = False
        self.layer_alpha = 0
        self.side = PreviewSide.FRONT

    def render(self, _values, base_dir: Path, options) -> PreviewResult:
        self.base_dir = base_dir
        self.aux_layer = options.aux_layer
        self.gcode_trace = options.gcode_trace
        self.show_gcode = options.show_gcode
        self.show_front = options.show_front
        self.show_back = options.show_back
        self.layer_alpha = options.layer_alpha
        self.side = options.side
        return PreviewResult(b"png", ["preview warning"], 2)


def test_app_build_constructs_initial_controls():
    page = FakePage()

    Pcb2GCodeApp(page).build()

    assert page.title == "PCB2GCode UI"
    assert page.services
    assert page.controls


def test_open_file_awaits_picker_and_loads_millproject(tmp_path: Path):
    millproject_path = tmp_path / "millproject"
    millproject_path.write_text("metric=true\nzsafe=5\n", encoding="utf-8")
    start_path = tmp_path / "previous"
    app = _app()
    app.working_directory = start_path
    app.file_picker = FakeFilePicker([FakeFile(str(millproject_path))])

    asyncio.run(app._open_file(None))

    assert app.current_millproject == millproject_path
    assert app.working_directory == tmp_path
    assert app.file_picker.kwargs["initial_directory"] == str(start_path)
    assert app.values["metric"] == "true"
    assert app.values["zsafe"] == "5"


def test_pick_input_file_sets_default_output_directory(tmp_path: Path):
    gerber_path = tmp_path / "board-F.Cu.gbr"
    start_path = tmp_path / "previous"
    app = _app()
    app.working_directory = start_path
    app.file_picker = FakeFilePicker([FakeFile(str(gerber_path))])
    app.controls["front"] = ft.TextField()
    app.controls["output-dir"] = ft.TextField()

    asyncio.run(app._pick_input_file(None, "front"))

    assert app.values["front"] == str(gerber_path)
    assert app.values["output-dir"] == str(tmp_path / "nc")
    assert app.working_directory == tmp_path
    assert app.file_picker.kwargs["initial_directory"] == str(start_path)


def test_pick_output_directory_awaits_picker(tmp_path: Path):
    output_path = tmp_path / "nc"
    start_path = tmp_path / "previous"
    app = _app()
    app.working_directory = start_path
    app.directory_picker = FakeDirectoryPicker(str(output_path))
    app.controls["output-dir"] = ft.TextField()

    asyncio.run(app._pick_output_directory(None))

    assert app.values["output-dir"] == str(output_path)
    assert app.working_directory == output_path
    assert app.directory_picker.kwargs["initial_directory"] == str(start_path)


def test_pick_output_directory_prefers_existing_output_dir(tmp_path: Path):
    output_path = tmp_path / "nc"
    start_path = tmp_path / "previous"
    existing_path = tmp_path / "existing-nc"
    app = _app()
    app.working_directory = start_path
    app.values["output-dir"] = str(existing_path)
    app.directory_picker = FakeDirectoryPicker(str(output_path))
    app.controls["output-dir"] = ft.TextField()

    asyncio.run(app._pick_output_directory(None))

    assert app.directory_picker.kwargs["initial_directory"] == str(existing_path)


def test_save_as_awaits_picker_and_writes_millproject(tmp_path: Path):
    millproject_path = tmp_path / "millproject"
    start_path = tmp_path / "previous"
    app = _app()
    app.working_directory = start_path
    app.values["metric"] = "true"
    app.save_picker = FakeSavePicker(str(millproject_path))

    asyncio.run(app._save_as(None))

    assert app.current_millproject == millproject_path
    assert app.working_directory == tmp_path
    assert app.save_picker.kwargs["initial_directory"] == str(start_path)
    assert parse_millproject(millproject_path)["metric"] == "true"


def test_save_as_prefers_current_millproject_directory(tmp_path: Path):
    project_path = tmp_path / "project" / "millproject"
    project_path.parent.mkdir()
    saved_path = tmp_path / "saved" / "millproject"
    saved_path.parent.mkdir()
    app = _app()
    app.current_millproject = project_path
    app.save_picker = FakeSavePicker(str(saved_path))

    asyncio.run(app._save_as(None))

    assert app.save_picker.kwargs["initial_directory"] == str(project_path.parent)
    assert app.working_directory == saved_path.parent


def test_refresh_preview_sets_image_data_uri():
    app = _app()
    app.preview_renderer = FakePreviewRenderer()
    app.preview_back.value = True
    app.preview_alpha.value = 70

    app._refresh_preview(None)

    assert app.preview_image.src.startswith("data:image/png;base64,")
    assert "2 layer" in app.preview_status.value
    assert "preview warning" in app.preview_status.value
    assert app.preview_renderer.show_front is True
    assert app.preview_renderer.show_back is True
    assert app.preview_renderer.layer_alpha == 70


def test_preview_side_selector_updates_preview_side():
    app = _app()
    app.preview_renderer = FakePreviewRenderer()

    app._select_preview_side(FakeEvent(FakeSegmentedControl([PreviewSide.BACK])))

    assert app.preview_side == PreviewSide.BACK
    assert app.preview_renderer.side == PreviewSide.BACK


def test_open_preview_shows_dialog_and_refreshes():
    page = FakePage()
    app = Pcb2GCodeApp(page)
    app.preview_renderer = FakePreviewRenderer()

    app._open_preview(None)

    assert page.dialogs
    assert app.preview_dialog is page.dialogs[0]
    assert app.preview_image.src.startswith("data:image/png;base64,")


def test_preview_content_uses_three_compact_control_rows():
    app = _app()

    content = app._build_preview_content()
    first_row, second_row, third_row = content.controls[:3]
    preview_status, preview_canvas, gcode_status = content.controls[3:6]
    first_labels = [_button_label(control) for control in first_row.controls]
    second_labels = [_control_label(control) for control in second_row.controls]
    third_labels = [_control_label(control) for control in third_row.controls]

    assert "Transparency" not in first_labels
    assert "Aux" in first_labels
    assert "NC" in first_labels
    assert "Refresh" in first_labels
    assert "Help" in first_labels
    assert "Load Aux" not in first_labels
    assert "Load NC" not in first_labels
    assert "Regenerate" not in first_labels
    assert second_labels == ["Gerber:", "Front", "Back", "Drill", "Cutoff", "Aux"]
    assert third_labels == ["NC:", "Front", "Back", "Drill", "Milldrill", "Outline"]
    assert second_row.wrap is False
    assert third_row.wrap is False
    assert second_row.scroll == ft.ScrollMode.AUTO
    assert third_row.scroll == ft.ScrollMode.AUTO
    assert all(_is_default_checkbox(control) for control in second_row.controls[1:])
    assert all(_is_default_checkbox(control) for control in third_row.controls[1:])
    assert preview_status is app.preview_status
    interactive_viewer = preview_canvas.content.controls[0]
    assert isinstance(interactive_viewer, ft.InteractiveViewer)
    assert interactive_viewer.content is app.preview_image
    assert interactive_viewer.pan_enabled is True
    assert interactive_viewer.scale_enabled is True
    assert interactive_viewer.trackpad_scroll_causes_scale is True
    assert interactive_viewer.min_scale == 0.5
    assert interactive_viewer.max_scale == 8.0
    assert interactive_viewer.constrained is False
    assert preview_canvas.content.controls[1] is app.gcode_instrument_overlay
    assert gcode_status is app.gcode_status


def test_close_preview_pops_dialog():
    page = FakePage()
    app = Pcb2GCodeApp(page)
    app.preview_renderer = FakePreviewRenderer()
    app._open_preview(None)

    app._close_preview(None)

    assert page.dialogs == []


def test_general_help_opens_workflow_dialog():
    page = FakePage()
    app = Pcb2GCodeApp(page)

    app._open_general_help(None)

    assert page.dialogs
    assert page.dialogs[0].title.value == "PCB2GCode UI Help"
    assert "Generate NC" in page.dialogs[0].content.controls[0].value


def test_option_help_opens_matching_option_dialog():
    page = FakePage()
    app = Pcb2GCodeApp(page)

    app._open_option_help(None, "mill-diameters")

    assert page.dialogs
    assert page.dialogs[0].title.value == OPTION_HELP_BY_KEY["mill-diameters"].title
    assert "unsafe" in page.dialogs[0].content.controls[0].value


def test_preview_help_opens_control_and_color_legend():
    page = FakePage()
    app = Pcb2GCodeApp(page)

    app._open_preview_help(None)

    assert page.dialogs
    assert page.dialogs[0].title.value == "Preview Help"
    content = page.dialogs[0].content.controls
    markdown = content[0].value
    legend_title = content[1]
    legend_table = content[2]
    first_legend_row = legend_table.controls[1].content.controls
    first_color_cell = first_legend_row[1]
    first_color_swatch = first_color_cell.controls[0]

    assert "G-code preview is a visual aid" in markdown
    assert legend_title.value == "Color Legend"
    assert first_legend_row[0].value == "Front copper"
    assert first_color_swatch.bgcolor == "#23DC96"
    assert first_color_cell.controls[1].value == "#23DC96"
    assert any(
        row.content.controls[0].value == "Retract / travel G-code"
        for row in legend_table.controls
    )


def test_file_row_includes_help_button_without_breaking_browse_button():
    app = _app()

    row = app._build_file_row(SPEC_BY_KEY["front"])

    assert any(isinstance(control, ft.IconButton) for control in row.controls)
    assert any(isinstance(control, ft.OutlinedButton) for control in row.controls)


def test_pick_aux_layer_is_preview_only_and_single_file(tmp_path: Path):
    aux_path = tmp_path / "board-F.SilkS.gbr"
    start_path = tmp_path / "previous"
    app = _app()
    app.working_directory = start_path
    app.preview_renderer = FakePreviewRenderer()
    app.other_layer_picker = FakeFilePicker([FakeFile(str(aux_path))])

    asyncio.run(app._pick_aux_layer(None))

    assert app.preview_aux_layer == aux_path
    assert app.working_directory == tmp_path
    assert app.other_layer_picker.kwargs["initial_directory"] == str(start_path)
    assert app.preview_renderer.aux_layer == aux_path


def test_base_dir_uses_working_directory_until_project_is_open(tmp_path: Path):
    working_path = tmp_path / "working"
    project_path = tmp_path / "project" / "millproject"
    app = _app()
    app.working_directory = working_path

    assert app._base_dir() == working_path

    app.current_millproject = project_path

    assert app._base_dir() == project_path.parent


def test_load_gcode_outputs_reads_configured_nc_files(tmp_path: Path):
    output_dir = tmp_path / "nc"
    output_dir.mkdir()
    (output_dir / "front.ngc").write_text(
        "G21\nT1 M6\nG0 X0 Y0 Z1\nG1 Z-0.1\nX1\nT1 M6\nX2\n",
        encoding="utf-8",
    )
    app = _app()
    app.preview_renderer = FakePreviewRenderer()
    app.values["output-dir"] = str(output_dir)
    app.preview_gcode_back.value = False
    app.preview_gcode_drill.value = False
    app.preview_gcode_milldrill.value = False
    app.preview_gcode_outline.value = False

    app._load_gcode_outputs(None)

    assert app.preview_gcode.value is True
    assert app.gcode_trace
    assert "4 segment" in app.gcode_status.value
    assert app.preview_renderer.show_gcode is True
    assert app.preview_renderer.gcode_trace.segments
    assert app.gcode_instrument_overlay.visible is True
    rows = app.gcode_instrument_overlay.content.controls
    assert rows[0].value == "NC tools"
    assert rows[1].controls[0].value == "Path"
    assert rows[2].content.value == "front.ngc"
    assert rows[3].controls[0].value == "1"
    assert rows[3].controls[1].value == "1"
    assert rows[3].controls[2].value == "3"
    assert rows[3].controls[3].value == "1"
    assert rows[3].controls[0].color == gcode_instrument_color(0)
    assert len(rows) == 4


def test_gcode_instrument_overlay_separates_nc_files():
    app = _app()
    front_trace = GcodeInterpreter().parse("G21\nT1 M6\nG1 X1 Z-0.1\n", "front")
    back_trace = GcodeInterpreter().parse("G21\nT2 M6\nG1 X2 Z-0.1\n", "back")
    trace = GcodeTrace(
        [*front_trace.segments, *back_trace.segments],
        [],
        [*front_trace.instruments, *back_trace.instruments],
    )

    app._set_gcode_instrument_overlay(trace)

    rows = app.gcode_instrument_overlay.content.controls
    assert rows[2].content.value == "front"
    assert rows[3].controls[1].value == "1"
    assert rows[4].content.value == "back"
    assert rows[5].controls[1].value == "2"


def test_gcode_instrument_overlay_keeps_initial_tool_path():
    app = _app()
    trace = GcodeInterpreter().parse(
        "G21\nG0 X0 Y0 Z1\nT1 M6\nG1 Z-0.1\nX1\n",
        "front",
    )

    app._set_gcode_instrument_overlay(trace)

    rows = app.gcode_instrument_overlay.content.controls
    assert rows[2].content.value == "front"
    assert [row.controls[0].value for row in rows[3:]] == ["1"]
    assert [row.controls[1].value for row in rows[3:]] == ["1"]
    assert rows[3].controls[3].value == "0"


def test_gcode_instrument_overlay_skips_pass_only_changed_tool():
    app = _app()
    trace = GcodeInterpreter().parse(
        "G21\nT2 M6\nG0 X0 Y0 Z1\nT1 M6\nG1 Z-0.1\nX1\n",
        "front",
    )

    app._set_gcode_instrument_overlay(trace)

    rows = app.gcode_instrument_overlay.content.controls
    assert rows[2].content.value == "front"
    assert [row.controls[1].value for row in rows[3:]] == ["1"]
    assert trace.retract_count == 1


def test_gcode_visibility_checkbox_controls_render_options():
    app = _app()
    app.preview_renderer = FakePreviewRenderer()

    app._load_gcode_outputs(None)
    app.preview_gcode.value = False
    app._refresh_preview(None)

    assert app.preview_renderer.show_gcode is False
    assert app.preview_renderer.gcode_trace is None
    assert app.gcode_instrument_overlay.visible is False


def _app() -> Pcb2GCodeApp:
    return Pcb2GCodeApp(FakePage())


def _button_label(control: ft.Control) -> str:
    content = getattr(control, "content", None)
    return content if isinstance(content, str) else ""


def _control_label(control: ft.Control) -> str:
    value = getattr(control, "value", None)
    if isinstance(value, str):
        return value
    label = getattr(control, "label", None)
    if isinstance(label, str):
        return label
    label_value = getattr(label, "value", None)
    return label_value if isinstance(label_value, str) else ""


def _is_default_checkbox(control: ft.Control) -> bool:
    return (
        isinstance(control, ft.Checkbox)
        and control.width is None
        and control.height is None
        and control.visual_density is None
        and isinstance(control.label, str)
    )
