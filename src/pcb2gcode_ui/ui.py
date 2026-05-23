import base64
from functools import partial
from pathlib import Path

import flet as ft

from pcb2gcode_ui.gcode_preview import (
    GcodeTrace,
    gcode_instrument_color,
    gcode_trace_summary,
    load_gcode_trace,
)
from pcb2gcode_ui.help_content import (
    GENERAL_HELP,
    OPTION_HELP_BY_KEY,
    PREVIEW_COLOR_LEGEND,
    PREVIEW_HELP,
    PreviewColorLegendEntry,
    option_help_markdown,
)
from pcb2gcode_ui.millproject import parse_millproject, write_millproject
from pcb2gcode_ui.options import (
    FILE_OPTIONS,
    OPTION_SPECS,
    SPEC_BY_KEY,
    OptionSpec,
    bool_value,
    default_output_directory,
    default_values,
)
from pcb2gcode_ui.preview import (
    DEFAULT_LAYER_ALPHA,
    GerberPreviewRenderer,
    PreviewOptions,
    PreviewResult,
    PreviewSide,
)
from pcb2gcode_ui.runner import (
    CommandResult,
    discover_binary,
    generate_nc_files,
    pcb2gcode_version,
    validate_with_binary,
)
from pcb2gcode_ui.validation import ValidationMessage, validate_values

FIELD_WIDTH = 520
BUTTON_WIDTH = 140
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 700
WINDOW_MIN_HEIGHT = 300
PREVIEW_DIALOG_WIDTH = 960
PREVIEW_DIALOG_HEIGHT = 680
PREVIEW_IMAGE_WIDTH = 920
PREVIEW_IMAGE_HEIGHT = 520
PREVIEW_ALPHA_SLIDER_WIDTH = 170
HELP_DIALOG_WIDTH = 760
HELP_DIALOG_HEIGHT = 520
HELP_ICON_SIZE = 16
HELP_BUTTON_SIZE = 32
LEGEND_LABEL_WIDTH = 190
LEGEND_COLOR_WIDTH = 150
LEGEND_SWATCH_SIZE = 18
INSTRUMENT_OVERLAY_WIDTH = 330
INSTRUMENT_SWATCH_SIZE = 14
BODY_TEXT_SIZE = 12
SMALL_TEXT_SIZE = 11
SECTION_TITLE_SIZE = 15
LABEL_TEXT_SIZE = 12
PAGE_BACKGROUND_COLOR = ft.Colors.GREY_900
SURFACE_COLOR = ft.Colors.GREY_800
FIELD_BACKGROUND_COLOR = ft.Colors.GREY_900
TEXT_COLOR = ft.Colors.GREY_100
MUTED_TEXT_COLOR = ft.Colors.GREY_300
OUTLINE_COLOR = ft.Colors.BLUE_GREY_300
FOCUSED_OUTLINE_COLOR = ft.Colors.LIGHT_BLUE_300
APP_SUMMARY = (
    "PCB2GCode UI is a lightweight editor for pcb2gcode millproject files. "
    "Use it to pick Gerber/drill inputs, tune common parameters, validate the command, "
    "and generate NC files without manually editing long option lists."
)


class Pcb2GCodeApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.values = default_values()
        self.controls: dict[str, ft.Control] = {}
        self.current_millproject: Path = None
        self.working_directory = Path.cwd()
        self.file_picker = ft.FilePicker()
        self.other_layer_picker = ft.FilePicker()
        self.directory_picker = ft.FilePicker()
        self.save_picker = ft.FilePicker()
        self.preview_renderer = GerberPreviewRenderer()
        self.preview_aux_layer: Path = None
        self.gcode_trace: GcodeTrace = None
        self.preview_side = PreviewSide.FRONT
        self.preview_front = ft.Checkbox(
            label="Front",
            value=True,
            on_change=self._update_preview_options,
        )
        self.preview_back = ft.Checkbox(
            label="Back",
            value=False,
            on_change=self._update_preview_options,
        )
        self.preview_drill = ft.Checkbox(
            label="Drill",
            value=True,
            on_change=self._update_preview_options,
        )
        self.preview_cutoff = ft.Checkbox(
            label="Cutoff",
            value=True,
            on_change=self._update_preview_options,
        )
        self.preview_other = ft.Checkbox(
            label="Aux",
            value=True,
            on_change=self._update_preview_options,
        )
        self.preview_gcode = ft.Checkbox(
            label="G-code",
            value=False,
            on_change=self._update_preview_options,
        )
        self.preview_gcode_front = self._gcode_checkbox("Front")
        self.preview_gcode_back = self._gcode_checkbox("Back")
        self.preview_gcode_drill = self._gcode_checkbox("Drill")
        self.preview_gcode_milldrill = self._gcode_checkbox("Milldrill")
        self.preview_gcode_outline = self._gcode_checkbox("Outline")
        self.preview_alpha = ft.Slider(
            value=DEFAULT_LAYER_ALPHA,
            min=10,
            max=100,
            divisions=9,
            label="{value}%",
            width=PREVIEW_ALPHA_SLIDER_WIDTH,
            active_color=FOCUSED_OUTLINE_COLOR,
            inactive_color=OUTLINE_COLOR,
            thumb_color=FOCUSED_OUTLINE_COLOR,
            on_change_end=self._update_preview_options,
        )
        self.preview_status = ft.Text(
            "Preview is not rendered yet.",
            color=MUTED_TEXT_COLOR,
            size=BODY_TEXT_SIZE,
        )
        self.gcode_status = ft.Text(
            "G-code is not loaded.",
            color=MUTED_TEXT_COLOR,
            size=BODY_TEXT_SIZE,
        )
        self.preview_image = ft.Image(
            b"",
            fit=ft.BoxFit.CONTAIN,
            width=PREVIEW_IMAGE_WIDTH,
            height=PREVIEW_IMAGE_HEIGHT,
        )
        self.gcode_instrument_overlay = ft.Container(
            visible=False,
            right=10,
            top=10,
            width=INSTRUMENT_OVERLAY_WIDTH,
            padding=8,
            bgcolor=SURFACE_COLOR,
            border=_border_all(),
            border_radius=4,
        )
        self.preview_dialog: ft.AlertDialog = None
        self.help_dialog: ft.AlertDialog = None
        self.status_text = ft.Text(color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE)
        self.group_container = ft.Column(spacing=8)
        self.group_controls: dict[str, ft.Control] = {}
        self.command_output = ft.TextField(
            label="Command output",
            multiline=True,
            min_lines=8,
            max_lines=12,
            read_only=True,
            expand=True,
            **_text_field_style(),
        )

    def build(self):
        self.page.title = "PCB2GCode UI"
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.bgcolor = PAGE_BACKGROUND_COLOR
        self.page.theme_mode = ft.ThemeMode.DARK
        self._configure_window()
        self.page.theme = ft.Theme(
            text_theme=ft.TextTheme(
                body_large=ft.TextStyle(size=BODY_TEXT_SIZE, color=TEXT_COLOR),
                body_medium=ft.TextStyle(size=BODY_TEXT_SIZE, color=TEXT_COLOR),
                body_small=ft.TextStyle(size=BODY_TEXT_SIZE, color=TEXT_COLOR),
                label_large=ft.TextStyle(size=LABEL_TEXT_SIZE, color=TEXT_COLOR),
                label_medium=ft.TextStyle(size=LABEL_TEXT_SIZE, color=TEXT_COLOR),
                label_small=ft.TextStyle(size=LABEL_TEXT_SIZE, color=TEXT_COLOR),
                title_medium=ft.TextStyle(size=SECTION_TITLE_SIZE, color=TEXT_COLOR),
            ),
            visual_density=ft.VisualDensity.COMPACT,
        )
        self.page.services.extend(
            [self.file_picker, self.other_layer_picker, self.directory_picker, self.save_picker]
        )
        self._refresh_binary_status()
        self.page.add(
            ft.Column(
                [
                    self._build_toolbar(),
                    self._build_summary(),
                    self.status_text,
                    self._build_file_section(),
                    self._build_parameter_sections(),
                    self.command_output,
                ],
                spacing=12,
            )
        )

    def _build_toolbar(self) -> ft.Control:
        return ft.Row(
            [
                ft.FilledButton(
                    "Open Millproject", icon=ft.Icons.FOLDER_OPEN, on_click=self._open_file
                ),
                ft.OutlinedButton(
                    "Save", icon=ft.Icons.SAVE, on_click=self._save, style=_button_style()
                ),
                ft.OutlinedButton(
                    "Save As", icon=ft.Icons.SAVE_AS, on_click=self._save_as, style=_button_style()
                ),
                ft.OutlinedButton(
                    "Validate", icon=ft.Icons.CHECK, on_click=self._validate, style=_button_style()
                ),
                ft.OutlinedButton(
                    "Preview",
                    icon=ft.Icons.IMAGE_SEARCH,
                    on_click=self._open_preview,
                    style=_button_style(),
                ),
                ft.OutlinedButton(
                    "Help",
                    icon=ft.Icons.HELP_OUTLINE,
                    on_click=self._open_general_help,
                    style=_button_style(),
                ),
                ft.FilledButton("Generate NC", icon=ft.Icons.PLAY_ARROW, on_click=self._generate),
            ],
            wrap=True,
        )

    def _build_summary(self) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                APP_SUMMARY,
                color=MUTED_TEXT_COLOR,
                size=BODY_TEXT_SIZE,
            ),
            padding=10,
            border=_border_all(),
            border_radius=6,
            bgcolor=SURFACE_COLOR,
        )

    def _build_preview_content(self) -> ft.Control:
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.SegmentedButton(
                            segments=[
                                ft.Segment(value=PreviewSide.FRONT, label=_tab_label("Front")),
                                ft.Segment(value=PreviewSide.BACK, label=_tab_label("Back")),
                            ],
                            selected=[self.preview_side],
                            on_change=self._select_preview_side,
                        ),
                        self.preview_alpha,
                        ft.OutlinedButton(
                            "Aux",
                            icon=ft.Icons.LAYERS,
                            on_click=self._pick_aux_layer,
                            style=_button_style(),
                        ),
                        ft.OutlinedButton(
                            "NC",
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=self._load_gcode_outputs,
                            style=_button_style(),
                        ),
                        ft.FilledButton(
                            "Refresh",
                            icon=ft.Icons.REFRESH,
                            on_click=self._refresh_preview,
                        ),
                        ft.OutlinedButton(
                            "Help",
                            icon=ft.Icons.HELP_OUTLINE,
                            on_click=self._open_preview_help,
                            style=_button_style(),
                        ),
                    ],
                    wrap=True,
                ),
                ft.Row(
                    [
                        ft.Text("Gerber:", color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE),
                        self.preview_front,
                        self.preview_back,
                        self.preview_drill,
                        self.preview_cutoff,
                        self.preview_other,
                    ],
                    wrap=False,
                    scroll=ft.ScrollMode.AUTO,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text("NC:", color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE),
                        self.preview_gcode_front,
                        self.preview_gcode_back,
                        self.preview_gcode_drill,
                        self.preview_gcode_milldrill,
                        self.preview_gcode_outline,
                    ],
                    wrap=False,
                    scroll=ft.ScrollMode.AUTO,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.preview_status,
                ft.Container(
                    content=ft.Stack(
                        [
                            self.preview_image,
                            self.gcode_instrument_overlay,
                        ],
                        width=PREVIEW_IMAGE_WIDTH,
                        height=PREVIEW_IMAGE_HEIGHT,
                    ),
                    padding=8,
                    border=_border_all(),
                    border_radius=4,
                    bgcolor=PAGE_BACKGROUND_COLOR,
                ),
                self.gcode_status,
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            width=PREVIEW_DIALOG_WIDTH,
            height=PREVIEW_DIALOG_HEIGHT,
        )

    def _build_preview_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=False,
            title=ft.Text("Preview", color=TEXT_COLOR, size=SECTION_TITLE_SIZE),
            content=ft.Column(
                [self._build_preview_content()],
                tight=True,
            ),
            bgcolor=SURFACE_COLOR,
            actions=[
                ft.OutlinedButton("Close", icon=ft.Icons.CLOSE, on_click=self._close_preview),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _build_file_section(self) -> ft.Control:
        rows = [
            self._build_file_row(SPEC_BY_KEY[key]) for key in ("front", "back", "drill", "outline")
        ]
        rows.append(self._build_output_directory_row())
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Files",
                        color=TEXT_COLOR,
                        size=SECTION_TITLE_SIZE,
                        weight=ft.FontWeight.BOLD,
                    ),
                    *rows,
                ]
            ),
            padding=10,
            border=_border_all(),
            border_radius=6,
            bgcolor=SURFACE_COLOR,
        )

    def _build_file_row(self, spec: OptionSpec) -> ft.Control:
        field = self._text_field(spec)

        return ft.Row(
            [
                field,
                self._help_button(spec),
                ft.OutlinedButton(
                    "Browse",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=partial(self._pick_input_file, key=spec.key),
                    width=BUTTON_WIDTH,
                    style=_button_style(),
                ),
            ]
        )

    def _build_output_directory_row(self) -> ft.Control:
        field = self._text_field(SPEC_BY_KEY["output-dir"])

        return ft.Row(
            [
                field,
                self._help_button(SPEC_BY_KEY["output-dir"]),
                ft.OutlinedButton(
                    "Browse",
                    icon=ft.Icons.FOLDER,
                    on_click=self._pick_output_directory,
                    width=BUTTON_WIDTH,
                    style=_button_style(),
                ),
            ]
        )

    def _build_parameter_sections(self) -> ft.Control:
        groups = []
        for spec in OPTION_SPECS:
            if (
                spec.group not in groups
                and spec.key not in FILE_OPTIONS
                and spec.key != "output-dir"
            ):
                groups.append(spec.group)
        tab_groups = [group for group in groups if group != "Files"]
        self.group_controls = {group: self._build_group(group) for group in tab_groups}
        self.group_container.controls = [self.group_controls[tab_groups[0]]]
        return ft.Column(
            [
                ft.SegmentedButton(
                    segments=[
                        ft.Segment(value=group, label=_tab_label(group))
                        for group in tab_groups
                    ],
                    selected=[tab_groups[0]],
                    on_change=self._select_parameter_group,
                ),
                self.group_container,
            ],
            spacing=10,
        )

    def _select_parameter_group(self, event):
        selected = list(event.control.selected)
        if not selected:
            return
        group = selected[0]
        self.group_container.controls = [self.group_controls[group]]
        self.page.update()

    def _update_preview_options(self, event):
        self._refresh_preview(event)

    def _select_preview_side(self, event):
        selected = list(event.control.selected)
        if not selected:
            return
        self.preview_side = PreviewSide(selected[0])
        self._refresh_preview(event)

    def _build_group(self, group: str) -> ft.Control:
        rows = [
            self._build_option_row(spec)
            for spec in OPTION_SPECS
            if spec.group == group and spec.key not in FILE_OPTIONS and spec.key != "output-dir"
        ]
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        group,
                        color=TEXT_COLOR,
                        size=SECTION_TITLE_SIZE,
                        weight=ft.FontWeight.BOLD,
                    ),
                    *rows,
                ],
                spacing=8,
            ),
            padding=10,
            border=_border_all(),
            border_radius=6,
            bgcolor=SURFACE_COLOR,
        )

    def _build_option_row(self, spec: OptionSpec) -> ft.Control:
        return ft.Row(
            [self._control_for_spec(spec), self._help_button(spec)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _control_for_spec(self, spec: OptionSpec) -> ft.Control:
        if spec.kind == "bool":
            return self._checkbox(spec)
        if spec.kind == "choice":
            return self._dropdown(spec)
        return self._text_field(spec)

    def _text_field(self, spec: OptionSpec) -> ft.TextField:
        field = ft.TextField(
            label=spec.label,
            value=self.values.get(spec.key, ""),
            tooltip=spec.help_text,
            width=FIELD_WIDTH,
            on_change=lambda event, key=spec.key: self._set_value(key, event.control.value, False),
            **_text_field_style(),
        )
        self.controls[spec.key] = field
        return field

    def _checkbox(self, spec: OptionSpec) -> ft.Checkbox:
        checkbox = ft.Checkbox(
            label=spec.label,
            value=bool_value(self.values.get(spec.key, "false")),
            tooltip=spec.help_text,
            label_style=ft.TextStyle(size=LABEL_TEXT_SIZE, color=TEXT_COLOR),
            on_change=lambda event, key=spec.key: self._set_value(
                key,
                "true" if event.control.value else "false",
                False,
            ),
        )
        self.controls[spec.key] = checkbox
        return checkbox

    def _dropdown(self, spec: OptionSpec) -> ft.Dropdown:
        dropdown = ft.Dropdown(
            label=spec.label,
            value=self.values.get(spec.key, ""),
            options=[ft.DropdownOption(key=choice, text=choice) for choice in spec.choices],
            tooltip=spec.help_text,
            width=FIELD_WIDTH,
            on_select=lambda event, key=spec.key: self._set_value(key, event.control.value, False),
            **_dropdown_style(),
        )
        self.controls[spec.key] = dropdown
        return dropdown

    def _gcode_checkbox(self, label: str) -> ft.Checkbox:
        return ft.Checkbox(
            label=label,
            value=True,
            on_change=self._update_preview_options,
        )

    def _help_button(self, spec: OptionSpec) -> ft.IconButton:
        return ft.IconButton(
            icon=ft.Icons.QUESTION_MARK,
            icon_color=FOCUSED_OUTLINE_COLOR,
            icon_size=HELP_ICON_SIZE,
            width=HELP_BUTTON_SIZE,
            height=HELP_BUTTON_SIZE,
            tooltip=f"Help for {spec.label}",
            on_click=partial(self._open_option_help, key=spec.key),
        )

    def _open_general_help(self, _event):
        self._show_help_dialog(GENERAL_HELP.title, GENERAL_HELP.markdown)

    def _open_preview_help(self, _event):
        self.help_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text(PREVIEW_HELP.title, color=TEXT_COLOR, size=SECTION_TITLE_SIZE),
            content=ft.Column(
                [
                    _help_markdown(PREVIEW_HELP.markdown),
                    ft.Text("Color Legend", color=TEXT_COLOR, size=SECTION_TITLE_SIZE),
                    _preview_color_legend_table(),
                ],
                width=HELP_DIALOG_WIDTH,
                height=HELP_DIALOG_HEIGHT,
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
            ),
            bgcolor=SURFACE_COLOR,
            actions=[
                ft.OutlinedButton(
                    "Close",
                    icon=ft.Icons.CLOSE,
                    on_click=self._close_help,
                    style=_button_style(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.help_dialog)
        self.page.update()

    def _open_option_help(self, _event, key: str):
        help_entry = OPTION_HELP_BY_KEY[key]
        self._show_help_dialog(help_entry.title, option_help_markdown(help_entry))

    def _show_help_dialog(self, title: str, markdown: str):
        self.help_dialog = ft.AlertDialog(
            modal=False,
            title=ft.Text(title, color=TEXT_COLOR, size=SECTION_TITLE_SIZE),
            content=ft.Column(
                [
                    _help_markdown(markdown),
                ],
                width=HELP_DIALOG_WIDTH,
                height=HELP_DIALOG_HEIGHT,
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=SURFACE_COLOR,
            actions=[
                ft.OutlinedButton(
                    "Close",
                    icon=ft.Icons.CLOSE,
                    on_click=self._close_help,
                    style=_button_style(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.help_dialog)
        self.page.update()

    def _close_help(self, _event):
        self.page.pop_dialog()
        self.page.update()

    def _set_value(self, key: str, value: str, update_control: bool = True):
        self.values[key] = value
        control = self.controls.get(key)
        if update_control and control:
            if isinstance(control, ft.Checkbox):
                control.value = bool_value(value or "false")
            else:
                control.value = value
        self._clear_control_error(key)
        self.page.update()

    def _set_default_output_dir(self):
        if not self.values.get("output-dir", "").strip():
            self._set_value("output-dir", str(default_output_directory(self.values)))

    async def _pick_input_file(self, _event, key: str):
        selected_files = await self.file_picker.pick_files(
            dialog_title=f"Select {SPEC_BY_KEY[key].label}",
            initial_directory=str(self.working_directory),
            allow_multiple=False,
        )
        if not selected_files:
            return
        selected_path = selected_files[0].path
        if not selected_path:
            self._set_output("Selected file has no local filesystem path.")
            return
        path = Path(selected_path)
        self._set_working_directory(path.parent)
        self._set_value(key, selected_path)
        self._set_default_output_dir()

    async def _pick_output_directory(self, _event):
        selected_path = await self.directory_picker.get_directory_path(
            dialog_title="Select NC output directory",
            initial_directory=self.values.get("output-dir", "") or str(self.working_directory),
        )
        if selected_path:
            self._set_working_directory(Path(selected_path))
            self._set_value("output-dir", selected_path)

    async def _pick_aux_layer(self, _event):
        selected_files = await self.other_layer_picker.pick_files(
            dialog_title="Select preview-only aux Gerber",
            initial_directory=str(self.working_directory),
            allow_multiple=False,
        )
        if not selected_files:
            return
        selected_path = selected_files[0].path
        if not selected_path:
            self.preview_status.value = "Selected aux Gerber has no local filesystem path."
            self.page.update()
            return
        self.preview_aux_layer = Path(selected_path)
        self._set_working_directory(self.preview_aux_layer.parent)
        self._refresh_preview(_event)

    def _load_gcode_outputs(self, event):
        self.gcode_trace = load_gcode_trace(
            self.values,
            self._base_dir(),
            self._selected_gcode_sources(),
        )
        self.preview_gcode.value = True
        self._set_gcode_status()
        self._refresh_preview(event)

    def _open_preview(self, event):
        if not self.preview_dialog:
            self.preview_dialog = self._build_preview_dialog()
        self.page.show_dialog(self.preview_dialog)
        self._refresh_preview(event)

    def _close_preview(self, _event):
        self.page.pop_dialog()
        self.page.update()

    async def _open_file(self, _event):
        selected_files = await self.file_picker.pick_files(
            dialog_title="Open millproject",
            initial_directory=str(self.working_directory),
            allow_multiple=False,
        )
        if not selected_files:
            return
        selected_path = selected_files[0].path
        if not selected_path:
            self._set_output("Selected millproject has no local filesystem path.")
            return
        path = Path(selected_path)
        self.current_millproject = path
        self._set_working_directory(path.parent)
        self.values = parse_millproject(path)
        for key, value in self.values.items():
            self._set_value(key, value)
        self._set_default_output_dir()
        self._set_output(f"Loaded {path}")

    async def _save(self, _event):
        if not self.current_millproject:
            await self._save_as(_event)
            return
        self._write_millproject(self.current_millproject)

    async def _save_as(self, _event):
        selected_path = await self.save_picker.save_file(
            dialog_title="Save millproject",
            file_name="millproject",
            initial_directory=str(self.current_millproject.parent)
            if self.current_millproject
            else str(self.working_directory),
        )
        if selected_path:
            self.current_millproject = Path(selected_path)
            self._set_working_directory(self.current_millproject.parent)
            self._write_millproject(self.current_millproject)

    def _write_millproject(self, path: Path):
        write_millproject(path, self.values)
        self._set_output(f"Saved {path}")

    def _validate(self, _event):
        messages = validate_values(self.values)
        self._show_validation_messages(messages)
        if messages:
            self._set_output("\n".join(message.text for message in messages))
            return
        result = validate_with_binary(self.values, base_dir=self._base_dir())
        self._set_command_result(result)

    def _generate(self, _event):
        messages = validate_values(self.values)
        self._show_validation_messages(messages)
        if messages:
            self._set_output("\n".join(message.text for message in messages))
            return
        validation_result = validate_with_binary(self.values, base_dir=self._base_dir())
        if not validation_result.ok:
            self._set_command_result(validation_result)
            return
        generation_result = generate_nc_files(self.values, base_dir=self._base_dir())
        self._set_command_result(generation_result)

    def _refresh_preview(self, _event):
        gcode_trace = None
        if self.gcode_trace and bool(self.preview_gcode.value):
            gcode_trace = self.gcode_trace.filtered(self._selected_gcode_sources())
        result = self.preview_renderer.render(
            self.values,
            self._base_dir(),
            PreviewOptions(
                side=self.preview_side,
                show_front=bool(self.preview_front.value),
                show_back=bool(self.preview_back.value),
                show_drill=bool(self.preview_drill.value),
                show_cutoff=bool(self.preview_cutoff.value),
                show_aux=bool(self.preview_other.value),
                show_gcode=bool(self.preview_gcode.value),
                aux_layer=self.preview_aux_layer,
                gcode_trace=gcode_trace,
                layer_alpha=round(self.preview_alpha.value),
            ),
        )
        self._set_gcode_instrument_overlay(gcode_trace)
        self._set_preview_result(result)

    def _set_preview_result(self, result: PreviewResult):
        if result.ok:
            self.preview_image.src = _png_data_uri(result.png)
            summary = f"Preview rendered with {result.layer_count} layer(s)."
        else:
            self.preview_image.src = b""
            summary = "Preview was not rendered."
        if result.warnings:
            summary = "\n".join([summary, *result.warnings])
        self.preview_status.value = summary
        self.page.update()

    def _set_gcode_status(self):
        if not self.gcode_trace:
            self.gcode_status.value = "G-code is not loaded."
            return
        lines = [gcode_trace_summary(self.gcode_trace)]
        if self.gcode_trace.warnings:
            lines.extend(self.gcode_trace.warnings[:4])
            if len(self.gcode_trace.warnings) > 4:
                lines.append(f"{len(self.gcode_trace.warnings) - 4} more warning(s).")
        self.gcode_status.value = "\n".join(lines)

    def _set_gcode_instrument_overlay(self, trace: GcodeTrace = None):
        if not trace or not trace.active_instruments:
            self.gcode_instrument_overlay.visible = False
            self.gcode_instrument_overlay.content = None
            return
        rows: list[ft.Control] = [
            ft.Text("NC instruments", color=TEXT_COLOR, size=BODY_TEXT_SIZE),
            _instrument_overlay_header(),
        ]
        for idx, instrument in enumerate(trace.active_instruments):
            cut_count, retract_count = trace.instrument_counts(instrument.id)
            rows.append(
                _instrument_overlay_row(
                    color=gcode_instrument_color(idx),
                    source_kind=instrument.source_kind,
                    change_index=instrument.change_index,
                    tool_id=instrument.tool_id,
                    cut_count=cut_count,
                    retract_count=retract_count,
                )
            )
        self.gcode_instrument_overlay.content = ft.Column(rows, spacing=4)
        self.gcode_instrument_overlay.visible = True

    def _selected_gcode_sources(self) -> set[str]:
        selected: set[str] = set()
        if self.preview_gcode_front.value:
            selected.add("front")
        if self.preview_gcode_back.value:
            selected.add("back")
        if self.preview_gcode_drill.value:
            selected.add("drill")
        if self.preview_gcode_milldrill.value:
            selected.add("milldrill")
        if self.preview_gcode_outline.value:
            selected.add("outline")
        return selected

    def _show_validation_messages(self, messages: list[ValidationMessage]):
        for control in self.controls.values():
            if isinstance(control, ft.TextField):
                control.error = None
            elif isinstance(control, ft.Dropdown):
                control.error_text = None
        for message in messages:
            control = self.controls.get(message.key)
            if isinstance(control, ft.TextField):
                control.error = message.text
            elif isinstance(control, ft.Dropdown):
                control.error_text = message.text
        self.page.update()

    def _clear_control_error(self, key: str):
        control = self.controls.get(key)
        if isinstance(control, ft.TextField):
            control.error = None
        elif isinstance(control, ft.Dropdown):
            control.error_text = None

    def _set_command_result(self, result: CommandResult):
        command = " ".join(result.command)
        status = "OK" if result.ok else f"Failed with exit code {result.return_code}"
        self._set_output(f"{status}\n\n{command}\n\n{result.output}")

    def _set_output(self, text: str):
        self.command_output.value = text
        self.page.update()

    def _refresh_binary_status(self):
        try:
            binary = discover_binary()
            result = pcb2gcode_version(binary)
            version = result.output.strip().splitlines()[0] if result.output.strip() else "unknown"
            self.status_text.value = f"pcb2gcode: {binary} ({version})"
        except FileNotFoundError as error:
            self.status_text.value = str(error)

    def _base_dir(self) -> Path:
        if self.current_millproject:
            return self.current_millproject.parent
        return self.working_directory

    def _set_working_directory(self, path: Path):
        self.working_directory = path

    def _configure_window(self):
        window = getattr(self.page, "window", None)
        if not window:
            return
        window.width = WINDOW_WIDTH
        window.height = WINDOW_HEIGHT
        window.min_width = WINDOW_MIN_WIDTH
        window.min_height = WINDOW_MIN_HEIGHT


def run_app():
    ft.app(target=lambda page: Pcb2GCodeApp(page).build())


def _border_all() -> ft.Border:
    side = ft.BorderSide(width=1, color=OUTLINE_COLOR)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def _help_markdown(markdown: str) -> ft.Markdown:
    return ft.Markdown(
        markdown,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        auto_follow_links=True,
    )


def _preview_color_legend_table() -> ft.Column:
    rows: list[ft.Control] = [_preview_color_legend_header()]
    rows.extend(_preview_color_legend_row(item) for item in PREVIEW_COLOR_LEGEND)
    return ft.Column(rows, spacing=0)


def _preview_color_legend_header() -> ft.Container:
    return _preview_color_legend_container(
        [
            ft.Text(
                "Layer / trace",
                width=LEGEND_LABEL_WIDTH,
                color=TEXT_COLOR,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                "Color",
                width=LEGEND_COLOR_WIDTH,
                color=TEXT_COLOR,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text("Meaning", expand=True, color=TEXT_COLOR, weight=ft.FontWeight.BOLD),
        ],
        SURFACE_COLOR,
    )


def _preview_color_legend_row(item: PreviewColorLegendEntry) -> ft.Container:
    return _preview_color_legend_container(
        [
            ft.Text(
                item.label,
                width=LEGEND_LABEL_WIDTH,
                color=TEXT_COLOR,
                size=BODY_TEXT_SIZE,
            ),
            ft.Row(
                [
                    ft.Container(
                        width=LEGEND_SWATCH_SIZE,
                        height=LEGEND_SWATCH_SIZE,
                        bgcolor=item.color,
                        border=_border_all(),
                        border_radius=2,
                    ),
                    ft.Text(item.color, color=TEXT_COLOR, size=BODY_TEXT_SIZE),
                ],
                width=LEGEND_COLOR_WIDTH,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(item.meaning, expand=True, color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE),
        ],
        FIELD_BACKGROUND_COLOR,
    )


def _preview_color_legend_container(
    controls: list[ft.Control],
    bgcolor: ft.ColorValue,
) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            controls,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=8,
        bgcolor=bgcolor,
        border=_border_all(),
    )


def _instrument_overlay_header() -> ft.Row:
    return ft.Row(
        [
            ft.Text("", width=INSTRUMENT_SWATCH_SIZE),
            _small_table_text("NC", 54, TEXT_COLOR),
            _small_table_text("Inst", 42, TEXT_COLOR),
            _small_table_text("Tool", 48, TEXT_COLOR),
            _small_table_text("Cut", 34, TEXT_COLOR),
            _small_table_text("Pass", 42, TEXT_COLOR),
        ],
        spacing=6,
    )


def _instrument_overlay_row(
    color: str,
    source_kind: str,
    change_index: int,
    tool_id: str,
    cut_count: int,
    retract_count: int,
) -> ft.Row:
    return ft.Row(
        [
            ft.Container(
                width=INSTRUMENT_SWATCH_SIZE,
                height=INSTRUMENT_SWATCH_SIZE,
                bgcolor=color,
                border=_border_all(),
            ),
            _small_table_text(source_kind, 54, MUTED_TEXT_COLOR),
            _small_table_text(str(change_index), 42, MUTED_TEXT_COLOR),
            _small_table_text(tool_id, 48, MUTED_TEXT_COLOR),
            _small_table_text(str(cut_count), 34, MUTED_TEXT_COLOR),
            _small_table_text(str(retract_count), 42, MUTED_TEXT_COLOR),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _small_table_text(value: str, width: int, color: ft.ColorValue) -> ft.Text:
    return ft.Text(
        value,
        width=width,
        color=color,
        size=SMALL_TEXT_SIZE,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def _tab_label(text: str) -> ft.Text:
    return ft.Text(
        text,
        color=TEXT_COLOR,
        size=BODY_TEXT_SIZE,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def _png_data_uri(png: bytes) -> str:
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _base_field_style() -> dict[str, object]:
    return {
        "border": ft.InputBorder.OUTLINE,
        "border_color": OUTLINE_COLOR,
        "focused_border_color": FOCUSED_OUTLINE_COLOR,
        "border_width": 1,
        "focused_border_width": 2,
        "border_radius": 4,
        "color": TEXT_COLOR,
        "fill_color": FIELD_BACKGROUND_COLOR,
        "filled": True,
        "label_style": ft.TextStyle(size=LABEL_TEXT_SIZE, color=MUTED_TEXT_COLOR),
        "text_size": BODY_TEXT_SIZE,
    }


def _text_field_style() -> dict[str, object]:
    return {
        **_base_field_style(),
        "cursor_color": FOCUSED_OUTLINE_COLOR,
    }


def _dropdown_style() -> dict[str, object]:
    return _base_field_style()


def _button_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        color=TEXT_COLOR,
        icon_color=TEXT_COLOR,
        side=ft.BorderSide(width=1, color=OUTLINE_COLOR),
    )
