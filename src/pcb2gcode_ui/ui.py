import base64
from functools import partial
from pathlib import Path

import flet as ft

from pcb2gcode_ui.app_state import AppSettings, load_app_settings, save_app_settings
from pcb2gcode_ui.gcode_preview import (
    GcodeInterpreter,
    GcodeTrace,
    gcode_cutoff_bounds,
    gcode_instrument_color,
    gcode_tool_sections,
    gcode_trace_summary,
    generated_output_paths,
    load_gcode_trace,
    write_gcode_tool_report,
)
from pcb2gcode_ui.help_content import (
    GENERAL_HELP,
    OPTION_HELP_BY_KEY,
    PREVIEW_COLOR_LEGEND,
    PREVIEW_HELP,
    PreviewColorLegendEntry,
    option_help_markdown,
)
from pcb2gcode_ui.millproject import (
    parse_millproject,
    validate_millproject_format,
    write_millproject,
)
from pcb2gcode_ui.options import (
    FILE_OPTIONS,
    OPTION_SPECS,
    SPEC_BY_KEY,
    OptionSpec,
    bool_value,
    default_output_directory,
    default_values,
)
from pcb2gcode_ui.postprocess import (
    POST_ORIGIN_BEFORE_M3_KEY,
    POST_REMOVE_T_KEY,
    post_process_generated_files,
)
from pcb2gcode_ui.preprocess import (
    PRE_ALIGN_DRILL_SOURCE_KEY,
    PRE_ALIGN_DRILLS_KEY,
    AlignDrillsPlan,
    PreProcessResult,
    align_drill_generation_values,
    align_drills_plan,
    pre_process_input_files,
)
from pcb2gcode_ui.preview import (
    DEFAULT_LAYER_ALPHA,
    GerberPreviewRenderer,
    PreviewOptions,
    PreviewResult,
    PreviewSide,
    transformed_gcode_cutoff_bounds_summary,
)
from pcb2gcode_ui.profile_loader import Profile, load_profiles
from pcb2gcode_ui.runner import (
    CommandResult,
    discover_binary,
    generate_nc_files,
    pcb2gcode_version,
    validate_with_binary,
)
from pcb2gcode_ui.validation import ValidationMessage, validate_values

FIELD_WIDTH = 520
PROFILE_FIELD_WIDTH = 190
PROFILE_DESCRIPTION_WIDTH = 360
BUTTON_WIDTH = 140
COMMAND_HISTORY_SEPARATOR = "\n\n---\n\n"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 700
WINDOW_MIN_HEIGHT = 300
PREVIEW_DIALOG_WIDTH = 960
PREVIEW_DIALOG_HEIGHT = 680
PREVIEW_IMAGE_WIDTH = 920
PREVIEW_IMAGE_HEIGHT = 520
PREVIEW_MIN_ZOOM = 0.5
PREVIEW_MAX_ZOOM = 8.0
PREVIEW_BOUNDARY_MARGIN = 1000
PREVIEW_ALPHA_SLIDER_WIDTH = 170
HELP_DIALOG_WIDTH = 760
HELP_DIALOG_HEIGHT = 520
HELP_ICON_SIZE = 16
HELP_BUTTON_SIZE = 32
LEGEND_LABEL_WIDTH = 190
LEGEND_COLOR_WIDTH = 150
LEGEND_SWATCH_SIZE = 18
INSTRUMENT_OVERLAY_WIDTH = 330
INSTRUMENT_OVERLAY_MARGIN = 10
CUTOFF_STATUS_EMPTY = "Cutoff bounds: no cutoff loaded."
CUSTOM_PROFILE_NAME = ""
CUSTOM_PROFILE_LABEL = "Custom"
PRE_PROCESS_OUTPUT_DIR_NAME = "pcb2gcode-ui-preprocess"
BODY_TEXT_SIZE = 12
SMALL_TEXT_SIZE = 11
SECTION_TITLE_SIZE = 15
LABEL_TEXT_SIZE = 12
PAGE_BACKGROUND_COLOR = ft.Colors.GREY_900
SURFACE_COLOR = ft.Colors.GREY_800
FIELD_BACKGROUND_COLOR = ft.Colors.GREY_900
TEXT_COLOR = ft.Colors.GREY_100
MUTED_TEXT_COLOR = ft.Colors.GREY_300
STALE_TEXT_COLOR = ft.Colors.RED_300
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
        self.app_settings = load_app_settings()
        self.default_millproject = self.app_settings.default_millproject
        self.working_directory = self.app_settings.last_directory
        self.profiles = load_profiles()
        self.profiles_by_name = {profile.name: profile for profile in self.profiles}
        self.selected_profile_name = (
            self.app_settings.selected_profile
            if self.app_settings.selected_profile in self.profiles_by_name
            else CUSTOM_PROFILE_NAME
        )
        self.generated_values_snapshot: dict[str, str] = None
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
        self.preview_gcode_align = self._gcode_checkbox("Align")
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
        self.cutoff_status = ft.Text(
            CUTOFF_STATUS_EMPTY,
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
            filter_quality=ft.FilterQuality.HIGH,
            width=PREVIEW_IMAGE_WIDTH,
            height=PREVIEW_IMAGE_HEIGHT,
        )
        self.preview_viewport = ft.InteractiveViewer(
            self.preview_image,
            width=PREVIEW_IMAGE_WIDTH,
            height=PREVIEW_IMAGE_HEIGHT,
            pan_enabled=True,
            scale_enabled=True,
            trackpad_scroll_causes_scale=True,
            min_scale=PREVIEW_MIN_ZOOM,
            max_scale=PREVIEW_MAX_ZOOM,
            constrained=False,
            boundary_margin=PREVIEW_BOUNDARY_MARGIN,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self.gcode_instrument_overlay = ft.Container(
            visible=False,
            width=INSTRUMENT_OVERLAY_WIDTH,
            padding=8,
            bgcolor=SURFACE_COLOR,
            border=_border_all(),
            border_radius=4,
        )
        self.gcode_instrument_left = (
            PREVIEW_IMAGE_WIDTH - INSTRUMENT_OVERLAY_WIDTH - INSTRUMENT_OVERLAY_MARGIN
        )
        self.gcode_instrument_top = INSTRUMENT_OVERLAY_MARGIN
        self.gcode_instrument_overlay_drag = ft.GestureDetector(
            content=self.gcode_instrument_overlay,
            left=self.gcode_instrument_left,
            top=self.gcode_instrument_top,
            mouse_cursor=ft.MouseCursor.MOVE,
            on_pan_update=self._pan_gcode_instrument_overlay,
        )
        self._apply_gcode_instrument_overlay_position()
        self.preview_dialog: ft.AlertDialog = None
        self.help_dialog: ft.AlertDialog = None
        self.status_text = ft.Text(color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE)
        self.generation_status = ft.Text(color=MUTED_TEXT_COLOR, size=BODY_TEXT_SIZE)
        self.profile_description = ft.Text(
            self._selected_profile_description(),
            color=MUTED_TEXT_COLOR,
            size=BODY_TEXT_SIZE,
            width=PROFILE_DESCRIPTION_WIDTH,
        )
        self.profile_dropdown = ft.Dropdown(
            label="Profile",
            value=self.selected_profile_name,
            options=[
                ft.DropdownOption(key=CUSTOM_PROFILE_NAME, text=CUSTOM_PROFILE_LABEL),
                *[
                    ft.DropdownOption(key=profile.name, text=profile.name)
                    for profile in self.profiles
                ],
            ],
            tooltip="Fixed machine profile.",
            width=PROFILE_FIELD_WIDTH,
            on_select=self._select_profile,
            **_dropdown_style(),
        )
        self._update_generation_status()
        self.group_container = ft.Column(spacing=8)
        self.group_controls: dict[str, ft.Control] = {}
        self.command_history_blocks: list[str] = []
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
                    self.generation_status,
                    self._build_file_section(),
                    self._build_parameter_sections(),
                    self.command_output,
                ],
                spacing=12,
            )
        )
        self._apply_selected_profile(mark_generated_stale=False)
        self._load_default_millproject_on_startup()

    def _build_toolbar(self) -> ft.Control:
        return ft.Row(
            [
                ft.Row(
                    [
                        ft.FilledButton(
                            "Open Millproject",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self._open_file,
                        ),
                        ft.OutlinedButton(
                            "Save", icon=ft.Icons.SAVE, on_click=self._save, style=_button_style()
                        ),
                        ft.OutlinedButton(
                            "Save As",
                            icon=ft.Icons.SAVE_AS,
                            on_click=self._save_as,
                            style=_button_style(),
                        ),
                        ft.OutlinedButton(
                            "Set Default",
                            icon=ft.Icons.STAR,
                            on_click=self._set_default_millproject,
                            style=_button_style(),
                        ),
                        ft.OutlinedButton(
                            "Reset to Default",
                            icon=ft.Icons.RESTART_ALT,
                            on_click=self._reset_to_default_millproject,
                            style=_button_style(),
                        ),
                        ft.OutlinedButton(
                            "Validate",
                            icon=ft.Icons.CHECK,
                            on_click=self._validate,
                            style=_button_style(),
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
                        self.profile_dropdown,
                        self.profile_description,
                    ],
                    wrap=True,
                    expand=True,
                ),
                ft.FilledButton("Generate NC", icon=ft.Icons.PLAY_ARROW, on_click=self._generate),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
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
                        self.preview_gcode_align,
                        self.preview_gcode_milldrill,
                        self.preview_gcode_outline,
                    ],
                    wrap=False,
                    scroll=ft.ScrollMode.AUTO,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.preview_status,
                self.cutoff_status,
                ft.Container(
                    content=ft.Stack(
                        [
                            self.preview_viewport,
                            self.gcode_instrument_overlay_drag,
                        ],
                        width=PREVIEW_IMAGE_WIDTH,
                        height=PREVIEW_IMAGE_HEIGHT,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
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
                        ft.Segment(value=group, label=_tab_label(group)) for group in tab_groups
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

    def _select_profile(self, event):
        self.selected_profile_name = event.control.value or CUSTOM_PROFILE_NAME
        self._apply_selected_profile()
        self._save_app_settings()

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

    def _set_value(
        self,
        key: str,
        value: str,
        update_control: bool = True,
        mark_generated_stale: bool = True,
        force_profile_value: bool = False,
    ):
        fixed_value = self._selected_profile_options().get(key)
        if fixed_value is not None and not force_profile_value:
            value = fixed_value
        self.values[key] = value
        control = self.controls.get(key)
        if update_control and control:
            if isinstance(control, ft.Checkbox):
                control.value = bool_value(value or "false")
            else:
                control.value = value
        self._clear_control_error(key)
        if mark_generated_stale:
            self._update_generation_status()
        self.page.update()

    def _selected_profile(self) -> Profile:
        return self.profiles_by_name.get(self.selected_profile_name)

    def _selected_profile_options(self) -> dict[str, str]:
        profile = self._selected_profile()
        if not profile:
            return {}
        return dict(profile.options)

    def _selected_profile_description(self) -> str:
        profile = self._selected_profile()
        if not profile:
            return "Profile: custom editable settings."
        return profile.description

    def _apply_selected_profile(self, mark_generated_stale: bool = True):
        self._apply_profile_values(mark_generated_stale=mark_generated_stale)
        self._apply_profile_control_locks()
        self.profile_dropdown.value = self.selected_profile_name
        self.profile_description.value = self._selected_profile_description()
        self.page.update()

    def _apply_profile_values(self, mark_generated_stale: bool = True):
        for key, value in self._selected_profile_options().items():
            self._set_value(
                key,
                value,
                mark_generated_stale=mark_generated_stale and self.values.get(key) != value,
                force_profile_value=True,
            )

    def _apply_profile_control_locks(self):
        fixed_keys = set(self._selected_profile_options())
        profile_keys = {key for profile in self.profiles for key in profile.options}
        for key in profile_keys:
            control = self.controls.get(key)
            if control:
                control.disabled = key in fixed_keys

    def _set_default_output_dir(self, mark_generated_stale: bool = True):
        if not self.values.get("output-dir", "").strip():
            self._set_value(
                "output-dir",
                str(default_output_directory(self.values)),
                mark_generated_stale=mark_generated_stale,
            )

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
        self._load_millproject(Path(selected_path), "Loaded")

    def _load_default_millproject_on_startup(self):
        if not self.default_millproject:
            return
        self._load_millproject(self.default_millproject, "Loaded default", fail_prefix="Default")

    def _set_default_millproject(self, _event):
        if not self.current_millproject:
            self._set_output("Open or save a millproject before setting it as default.")
            return
        self.default_millproject = self.current_millproject
        self._save_app_settings()
        self._set_output(f"Default millproject set to {self.current_millproject}")

    def _reset_to_default_millproject(self, _event):
        if not self.default_millproject:
            self._set_output("No default millproject is configured.")
            return
        self._load_millproject(self.default_millproject, "Reset to default", fail_prefix="Default")

    def _load_millproject(
        self,
        path: Path,
        success_prefix: str,
        fail_prefix: str = "Invalid",
    ) -> bool:
        format_messages = validate_millproject_format(path)
        if format_messages:
            self._set_output(_format_open_format_error(path, format_messages, fail_prefix))
            return False
        values = parse_millproject(path)
        messages = validate_values(values)
        if messages:
            self._show_validation_messages(messages)
            self._set_output(_format_open_validation_error(path, messages, fail_prefix))
            return False
        self.current_millproject = path
        self._set_working_directory(path.parent)
        self.values = values
        self._apply_profile_values(mark_generated_stale=False)
        for key, value in self.values.items():
            self._set_value(key, value, mark_generated_stale=False)
        self._apply_profile_control_locks()
        self._set_default_output_dir(mark_generated_stale=False)
        self._clear_generated_snapshot()
        self._set_output(f"{success_prefix} {path}")
        return True

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
        self._append_command_result("Validate", result)

    def _generate(self, _event):
        messages = validate_values(self.values)
        self._show_validation_messages(messages)
        if messages:
            self._set_output("\n".join(message.text for message in messages))
            return
        pre_process_plan = None
        if self._align_drills_enabled():
            first_pass_values = self._first_pass_pre_process_values()
            first_generation_result = generate_nc_files(
                first_pass_values,
                base_dir=self._base_dir(),
            )
            self._append_command_result("Pre-process outline generation", first_generation_result)
            if not first_generation_result.ok:
                return
            try:
                pre_process_plan = self._build_align_drills_plan(first_pass_values)
            except (OSError, ValueError) as error:
                self._append_process_log("Pre-process", f"Pre-process failed: {error}")
                return
            self._set_value("x-offset", pre_process_plan.x_offset)
            self._set_value("y-offset", pre_process_plan.y_offset)
            messages = validate_values(self.values)
            self._show_validation_messages(messages)
            if messages:
                self._append_process_log(
                    "Validation",
                    "\n".join(message.text for message in messages),
                )
                return
        try:
            pre_process_result = pre_process_input_files(
                self.values,
                self._base_dir(),
                self._generation_output_dir(),
                pre_process_plan,
            )
        except OSError as error:
            self._append_process_log("Pre-process", f"Pre-process failed: {error}")
            return
        self._append_process_log("Pre-process", pre_process_result.summary)
        if pre_process_result.values.get(PRE_ALIGN_DRILL_SOURCE_KEY, "").strip():
            self._set_value(
                PRE_ALIGN_DRILL_SOURCE_KEY,
                pre_process_result.values[PRE_ALIGN_DRILL_SOURCE_KEY],
                mark_generated_stale=False,
            )
        validation_result = validate_with_binary(
            pre_process_result.values,
            base_dir=self._base_dir(),
        )
        self._append_command_result("Validate", validation_result)
        if not validation_result.ok:
            return
        generation_result = generate_nc_files(
            pre_process_result.values,
            base_dir=self._base_dir(),
        )
        self._append_command_result("Generate NC", generation_result)
        if generation_result.ok:
            align_generation_result = self._generate_align_drill_nc(
                pre_process_result,
            )
            if not align_generation_result.ok:
                return
            if align_generation_result.command:
                generation_result = align_generation_result
        if generation_result.ok:
            post_process_ok = self._post_process_generated_files()
            if not post_process_ok:
                return
            report_ok = self._write_gcode_tool_report()
            if not report_ok:
                return
        if generation_result.ok:
            self.generated_values_snapshot = self._values_snapshot()
            self._reset_gcode_preview_after_generation()
            self._update_generation_status()
            self.page.update()

    def _generate_align_drill_nc(
        self,
        pre_process_result: PreProcessResult,
    ) -> CommandResult:
        if not bool_value(self.values.get(PRE_ALIGN_DRILLS_KEY, "false")):
            return CommandResult([], 0, "")
        if not pre_process_result.processed_files:
            return CommandResult([], 0, "")
        align_values = align_drill_generation_values(pre_process_result.values)
        result = generate_nc_files(align_values, base_dir=self._base_dir())
        self._append_command_result("Alignment drill NC (front side):", result)
        return result

    def _post_process_generated_files(self) -> bool:
        if not self._post_process_enabled():
            return True
        try:
            post_process_result = post_process_generated_files(self.values, self._base_dir())
        except OSError as error:
            self._append_process_log("Post-process", f"Post-process failed: {error}")
            return False
        self._append_process_log("Post-process", post_process_result.summary)
        return True

    def _post_process_enabled(self) -> bool:
        return bool_value(self.values.get(POST_REMOVE_T_KEY, "false")) or bool_value(
            self.values.get(POST_ORIGIN_BEFORE_M3_KEY, "false")
        )

    def _write_gcode_tool_report(self) -> bool:
        source_kinds = self._generated_gcode_source_kinds(self.values)
        if not source_kinds:
            return True
        try:
            result = write_gcode_tool_report(
                self.values,
                self._base_dir(),
                source_kinds,
            )
        except OSError as error:
            self._append_process_log("Tool report", f"Tool report failed: {error}")
            return False
        self._append_process_log("Tool report", result.summary)
        return True

    def _generated_gcode_source_kinds(self, values: dict[str, str]) -> set[str]:
        source_kinds: set[str] = set()
        for source_kind in ("front", "back", "drill", "outline"):
            if values.get(source_kind, "").strip():
                source_kinds.add(source_kind)
        if values.get("drill", "").strip() and any(
            values.get(key, "").strip()
            for key in ("milldrill-diameter", "min-milldrill-hole-diameter", "zmilldrill")
        ):
            source_kinds.add("milldrill")
        if values.get(PRE_ALIGN_DRILL_SOURCE_KEY, "").strip():
            source_kinds.add("align-drill")
        return source_kinds

    def _with_pre_process_summary(
        self,
        result: CommandResult,
        pre_process_result: PreProcessResult,
    ) -> CommandResult:
        if not bool_value(self.values.get(PRE_ALIGN_DRILLS_KEY, "false")):
            return result
        if not pre_process_result.processed_files:
            return result
        return CommandResult(
            result.command,
            result.return_code,
            f"{result.output}\n\n{pre_process_result.summary}",
        )

    def _align_drills_enabled(self) -> bool:
        return (
            bool_value(self.values.get(PRE_ALIGN_DRILLS_KEY, "false"))
            and bool(self.values.get("outline", "").strip())
        )

    def _first_pass_pre_process_values(self) -> dict[str, str]:
        values = dict(self.values)
        values["output-dir"] = str(self._pre_process_output_dir())
        return values

    def _pre_process_output_dir(self) -> Path:
        return self._generation_output_dir() / PRE_PROCESS_OUTPUT_DIR_NAME

    def _build_align_drills_plan(self, values: dict[str, str]) -> AlignDrillsPlan:
        outline_path = generated_output_paths(
            values,
            self._base_dir(),
            {"outline"},
        )[0]
        if not outline_path.exists():
            raise ValueError(f"generated outline file not found: {outline_path}")
        trace = GcodeInterpreter().parse_file(outline_path, "outline")
        bounds = gcode_cutoff_bounds(trace)
        if not bounds:
            raise ValueError(f"generated outline file has no cut segments: {outline_path}")
        return align_drills_plan(self.values, bounds)

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
                sizing_gcode_trace=self.gcode_trace,
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
            self.cutoff_status.value = CUTOFF_STATUS_EMPTY
            return
        lines = [gcode_trace_summary(self.gcode_trace)]
        cutoff_summary = transformed_gcode_cutoff_bounds_summary(
            self.gcode_trace,
            self.values,
            self.preview_side,
        )
        if cutoff_summary:
            self.cutoff_status.value = cutoff_summary
        else:
            self.cutoff_status.value = CUTOFF_STATUS_EMPTY
        if self.gcode_trace.warnings:
            lines.extend(self.gcode_trace.warnings[:4])
            if len(self.gcode_trace.warnings) > 4:
                lines.append(f"{len(self.gcode_trace.warnings) - 4} more warning(s).")
        self.gcode_status.value = "\n".join(lines)

    def _set_gcode_instrument_overlay(self, trace: GcodeTrace = None):
        tool_sections = gcode_tool_sections(trace) if trace else ()
        if not tool_sections:
            self.gcode_instrument_overlay.visible = False
            self.gcode_instrument_overlay.content = None
            return
        rows: list[ft.Control] = [
            ft.Text("NC tools", color=TEXT_COLOR, size=BODY_TEXT_SIZE),
        ]
        for section in tool_sections:
            rows.extend(
                [
                    _instrument_overlay_section_header(section.source_label),
                    _instrument_overlay_header(),
                ]
            )
            for row in section.rows:
                rows.append(
                    _instrument_overlay_row(
                        color=gcode_instrument_color(row.color_index),
                        path_index=row.path_index,
                        tool_id=row.tool_id,
                        bit_label=row.bit_label,
                        cut_count=row.cut_count,
                        retract_count=row.retract_count,
                    )
                )
        self.gcode_instrument_overlay.content = ft.Column(rows, spacing=4)
        self.gcode_instrument_overlay.visible = True
        self._apply_gcode_instrument_overlay_position()

    def _pan_gcode_instrument_overlay(self, event):
        delta = getattr(event, "local_delta", None) or getattr(event, "global_delta", None)
        self.gcode_instrument_left = _clamp(
            self.gcode_instrument_left + _offset_x(delta),
            0,
            PREVIEW_IMAGE_WIDTH - INSTRUMENT_OVERLAY_WIDTH,
        )
        self.gcode_instrument_top = _clamp(
            self.gcode_instrument_top + _offset_y(delta),
            0,
            PREVIEW_IMAGE_HEIGHT - INSTRUMENT_OVERLAY_MARGIN,
        )
        self._apply_gcode_instrument_overlay_position()
        self.page.update()

    def _apply_gcode_instrument_overlay_position(self):
        self.gcode_instrument_overlay_drag.left = self.gcode_instrument_left
        self.gcode_instrument_overlay_drag.top = self.gcode_instrument_top

    def _selected_gcode_sources(self) -> set[str]:
        selected: set[str] = set()
        if self.preview_gcode_front.value:
            selected.add("front")
        if self.preview_gcode_back.value:
            selected.add("back")
        if self.preview_gcode_drill.value:
            selected.add("drill")
        if self.preview_gcode_align.value and self._align_drill_preview_enabled():
            selected.add("align-drill")
        if self.preview_gcode_milldrill.value:
            selected.add("milldrill")
        if self.preview_gcode_outline.value:
            selected.add("outline")
        return selected

    def _align_drill_preview_enabled(self) -> bool:
        return bool_value(self.values.get(PRE_ALIGN_DRILLS_KEY, "false")) or bool(
            self.values.get(PRE_ALIGN_DRILL_SOURCE_KEY, "").strip()
        )

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
        self._set_output(self._format_command_result(result))

    def _append_command_result(self, title: str, result: CommandResult):
        self._append_command_history(title, self._format_command_result(result))

    def _append_process_log(self, title: str, text: str):
        self._append_command_history(title, text)

    def _append_command_history(self, title: str, body: str):
        content = "\n\n".join(item for item in (title, body.strip()) if item)
        self.command_history_blocks.append(content)
        self.command_output.value = COMMAND_HISTORY_SEPARATOR.join(self.command_history_blocks)
        self.page.update()

    def _format_command_result(self, result: CommandResult) -> str:
        command = " ".join(result.command)
        status = "OK" if result.ok else f"Failed with exit code {result.return_code}"
        working_directory = f"Working directory: {result.cwd}" if result.cwd else ""
        return "\n\n".join(
            item for item in (status, working_directory, command, result.output.strip()) if item
        )

    def _set_output(self, text: str):
        self.command_history_blocks = []
        self.command_output.value = text
        self.page.update()

    def _values_snapshot(self) -> dict[str, str]:
        return dict(self.values)

    def _clear_generated_snapshot(self):
        self.generated_values_snapshot = None
        self._reset_gcode_preview_after_generation()
        self._update_generation_status()

    def _update_generation_status(self):
        if self.generated_values_snapshot is None:
            self.generation_status.value = "NC: not generated for current session."
            self.generation_status.color = MUTED_TEXT_COLOR
        elif self.generated_values_snapshot == self._values_snapshot():
            self.generation_status.value = "NC: generated for current settings."
            self.generation_status.color = MUTED_TEXT_COLOR
        else:
            self.generation_status.value = "NC: generated output is stale; settings changed."
            self.generation_status.color = STALE_TEXT_COLOR

    def _reset_gcode_preview_after_generation(self):
        self.gcode_trace = None
        self.preview_gcode.value = False
        self._set_gcode_status()
        self._set_gcode_instrument_overlay(None)
        if self.preview_dialog:
            self._refresh_preview(None)

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

    def _generation_output_dir(self) -> Path:
        output_value = self.values.get("output-dir", "").strip()
        if not output_value:
            return default_output_directory(self.values)
        output_path = Path(output_value).expanduser()
        if output_path.is_absolute():
            return output_path
        return self._base_dir() / output_path

    def _set_working_directory(self, path: Path):
        self.working_directory = path
        self._save_app_settings()

    def _save_app_settings(self):
        save_app_settings(
            AppSettings(
                last_directory=self.working_directory,
                default_millproject=self.default_millproject,
                selected_profile=self.selected_profile_name,
            )
        )

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
            _small_table_text("Path", 42, TEXT_COLOR),
            _small_table_text("Tool", 38, TEXT_COLOR),
            _small_table_text("Bit", 92, TEXT_COLOR),
            _small_table_text("Cut", 34, TEXT_COLOR),
            _small_table_text("Pass", 42, TEXT_COLOR),
        ],
        spacing=6,
    )


def _instrument_overlay_section_header(source_label: str) -> ft.Text:
    return ft.Text(
        source_label,
        color=TEXT_COLOR,
        size=SMALL_TEXT_SIZE,
        weight=ft.FontWeight.BOLD,
        no_wrap=True,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def _instrument_overlay_row(
    color: str,
    path_index: int,
    tool_id: str,
    bit_label: str,
    cut_count: int,
    retract_count: int,
) -> ft.Row:
    return ft.Row(
        [
            _small_table_text(str(path_index), 42, color),
            _small_table_text(tool_id, 38, MUTED_TEXT_COLOR),
            _small_table_text(bit_label, 92, MUTED_TEXT_COLOR),
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


def _offset_x(offset) -> float:
    return float(getattr(offset, "x", 0) or 0)


def _offset_y(offset) -> float:
    return float(getattr(offset, "y", 0) or 0)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _format_open_validation_error(
    path: Path,
    messages: list[ValidationMessage],
    prefix: str = "Invalid",
) -> str:
    lines = [f"{prefix} millproject file: {path}", ""]
    lines.extend(f"{SPEC_BY_KEY[message.key].label}: {message.text}" for message in messages)
    return "\n".join(lines)


def _format_open_format_error(
    path: Path,
    messages: list[str],
    prefix: str = "Invalid",
) -> str:
    lines = [f"{prefix} millproject file format: {path}", ""]
    lines.extend(messages)
    return "\n".join(lines)


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
