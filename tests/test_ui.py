import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

from pcb2gcode_ui.millproject import parse_millproject
from pcb2gcode_ui.ui import Pcb2GCodeApp


@dataclass
class FakePage:
    title: str = ""
    scroll: object = None
    services: list[object] = field(default_factory=list)
    controls: list[object] = field(default_factory=list)

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass


@dataclass
class FakeFile:
    path: str


class FakeFilePicker:
    def __init__(self, selected_files: list[FakeFile] = None):
        self.selected_files = selected_files or []

    async def pick_files(self, **_kwargs) -> list[FakeFile]:
        return self.selected_files


class FakeDirectoryPicker:
    def __init__(self, selected_path: str = ""):
        self.selected_path = selected_path

    async def get_directory_path(self, **_kwargs) -> str:
        return self.selected_path


class FakeSavePicker:
    def __init__(self, selected_path: str = ""):
        self.selected_path = selected_path

    async def save_file(self, **_kwargs) -> str:
        return self.selected_path


def test_app_build_constructs_initial_controls():
    page = FakePage()

    Pcb2GCodeApp(page).build()

    assert page.title == "PCB2GCode UI"
    assert page.services
    assert page.controls


def test_open_file_awaits_picker_and_loads_millproject(tmp_path: Path):
    millproject_path = tmp_path / "millproject"
    millproject_path.write_text("metric=true\nzsafe=5\n", encoding="utf-8")
    app = _app()
    app.file_picker = FakeFilePicker([FakeFile(str(millproject_path))])

    asyncio.run(app._open_file(None))

    assert app.current_millproject == millproject_path
    assert app.values["metric"] == "true"
    assert app.values["zsafe"] == "5"


def test_pick_input_file_sets_default_output_directory(tmp_path: Path):
    gerber_path = tmp_path / "board-F.Cu.gbr"
    app = _app()
    app.file_picker = FakeFilePicker([FakeFile(str(gerber_path))])
    app.controls["front"] = ft.TextField()
    app.controls["output-dir"] = ft.TextField()

    asyncio.run(app._pick_input_file(None, "front"))

    assert app.values["front"] == str(gerber_path)
    assert app.values["output-dir"] == str(tmp_path / "nc")


def test_pick_output_directory_awaits_picker(tmp_path: Path):
    output_path = tmp_path / "nc"
    app = _app()
    app.directory_picker = FakeDirectoryPicker(str(output_path))
    app.controls["output-dir"] = ft.TextField()

    asyncio.run(app._pick_output_directory(None))

    assert app.values["output-dir"] == str(output_path)


def test_save_as_awaits_picker_and_writes_millproject(tmp_path: Path):
    millproject_path = tmp_path / "millproject"
    app = _app()
    app.values["metric"] = "true"
    app.save_picker = FakeSavePicker(str(millproject_path))

    asyncio.run(app._save_as(None))

    assert app.current_millproject == millproject_path
    assert parse_millproject(millproject_path)["metric"] == "true"


def _app() -> Pcb2GCodeApp:
    return Pcb2GCodeApp(FakePage())
