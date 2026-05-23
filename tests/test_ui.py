from dataclasses import dataclass, field

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


def test_app_build_constructs_initial_controls():
    page = FakePage()

    Pcb2GCodeApp(page).build()

    assert page.title == "PCB2GCode UI"
    assert page.services
    assert page.controls
