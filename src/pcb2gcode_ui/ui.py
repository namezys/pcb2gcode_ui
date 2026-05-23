from pathlib import Path

import flet as ft

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


class Pcb2GCodeApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.values = default_values()
        self.controls: dict[str, ft.Control] = {}
        self.current_millproject: Path = None
        self.file_picker = ft.FilePicker()
        self.directory_picker = ft.FilePicker()
        self.save_picker = ft.FilePicker()
        self.status_text = ft.Text()
        self.command_output = ft.TextField(
            label="Command output",
            multiline=True,
            min_lines=8,
            max_lines=12,
            read_only=True,
            expand=True,
        )

    def build(self):
        self.page.title = "PCB2GCode UI"
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.services.extend([self.file_picker, self.directory_picker, self.save_picker])
        self._refresh_binary_status()
        self.page.add(
            ft.Column(
                [
                    self._build_toolbar(),
                    self.status_text,
                    self._build_file_section(),
                    self._build_tabs(),
                    self.command_output,
                ],
                spacing=12,
                expand=True,
            )
        )

    def _build_toolbar(self) -> ft.Control:
        return ft.Row(
            [
                ft.FilledButton(
                    "Open Millproject", icon=ft.Icons.FOLDER_OPEN, on_click=self._open_file
                ),
                ft.OutlinedButton("Save", icon=ft.Icons.SAVE, on_click=self._save),
                ft.OutlinedButton("Save As", icon=ft.Icons.SAVE_AS, on_click=self._save_as),
                ft.OutlinedButton("Validate", icon=ft.Icons.CHECK, on_click=self._validate),
                ft.FilledButton("Generate NC", icon=ft.Icons.PLAY_ARROW, on_click=self._generate),
            ],
            wrap=True,
        )

    def _build_file_section(self) -> ft.Control:
        rows = [
            self._build_file_row(SPEC_BY_KEY[key]) for key in ("front", "back", "drill", "outline")
        ]
        rows.append(self._build_output_directory_row())
        return ft.Container(
            content=ft.Column([ft.Text("Files", size=18, weight=ft.FontWeight.BOLD), *rows]),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=6,
        )

    def _build_file_row(self, spec: OptionSpec) -> ft.Control:
        field = self._text_field(spec)

        def pick_file(_event, key: str = spec.key):
            selected_files = self.file_picker.pick_files(
                dialog_title=f"Select {SPEC_BY_KEY[key].label}",
                allow_multiple=False,
            )
            if selected_files:
                self._set_value(key, selected_files[0].path)
                self._set_default_output_dir()

        return ft.Row(
            [
                field,
                ft.OutlinedButton(
                    "Browse", icon=ft.Icons.UPLOAD_FILE, on_click=pick_file, width=BUTTON_WIDTH
                ),
            ]
        )

    def _build_output_directory_row(self) -> ft.Control:
        field = self._text_field(SPEC_BY_KEY["output-dir"])

        def pick_directory(_event):
            selected_path = self.directory_picker.get_directory_path(
                dialog_title="Select NC output directory",
                initial_directory=self.values.get("output-dir", ""),
            )
            if selected_path:
                self._set_value("output-dir", selected_path)

        return ft.Row(
            [
                field,
                ft.OutlinedButton(
                    "Browse", icon=ft.Icons.FOLDER, on_click=pick_directory, width=BUTTON_WIDTH
                ),
            ]
        )

    def _build_tabs(self) -> ft.Control:
        groups = []
        for spec in OPTION_SPECS:
            if (
                spec.group not in groups
                and spec.key not in FILE_OPTIONS
                and spec.key != "output-dir"
            ):
                groups.append(spec.group)
        return ft.Tabs(
            tabs=[
                ft.Tab(text=group, content=self._build_group(group))
                for group in groups
                if group != "Files"
            ],
            expand=True,
        )

    def _build_group(self, group: str) -> ft.Control:
        rows = [
            self._build_option_row(spec)
            for spec in OPTION_SPECS
            if spec.group == group and spec.key not in FILE_OPTIONS and spec.key != "output-dir"
        ]
        return ft.Container(
            content=ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8),
            padding=10,
        )

    def _build_option_row(self, spec: OptionSpec) -> ft.Control:
        return ft.Row(
            [self._control_for_spec(spec)], vertical_alignment=ft.CrossAxisAlignment.START
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
        )
        self.controls[spec.key] = field
        return field

    def _checkbox(self, spec: OptionSpec) -> ft.Checkbox:
        checkbox = ft.Checkbox(
            label=spec.label,
            value=bool_value(self.values.get(spec.key, "false")),
            tooltip=spec.help_text,
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
        )
        self.controls[spec.key] = dropdown
        return dropdown

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

    def _open_file(self, _event):
        selected_files = self.file_picker.pick_files(
            dialog_title="Open millproject",
            allow_multiple=False,
        )
        if not selected_files:
            return
        path = Path(selected_files[0].path)
        self.current_millproject = path
        self.values = parse_millproject(path)
        for key, value in self.values.items():
            self._set_value(key, value)
        self._set_default_output_dir()
        self._set_output(f"Loaded {path}")

    def _save(self, _event):
        if not self.current_millproject:
            self._save_as(_event)
            return
        self._write_millproject(self.current_millproject)

    def _save_as(self, _event):
        selected_path = self.save_picker.save_file(
            dialog_title="Save millproject",
            file_name="millproject",
            initial_directory=str(self.current_millproject.parent)
            if self.current_millproject
            else "",
        )
        if selected_path:
            self.current_millproject = Path(selected_path)
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
        return Path.cwd()


def run_app():
    ft.app(target=lambda page: Pcb2GCodeApp(page).build())
