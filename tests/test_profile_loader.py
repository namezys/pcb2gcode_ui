import logging
from pathlib import Path

from pcb2gcode_ui.profile_loader import load_profiles


def test_load_profiles_uses_filename_as_profile_name(tmp_path: Path):
    (tmp_path / "TestMachine.yaml").write_text(
        """
description: Test profile.
options:
  post-remove-t: true
  post-origin-before-m3: false
""",
        encoding="utf-8",
    )

    profiles = load_profiles(tmp_path)

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.name == "TestMachine"
    assert profile.description == "Test profile."
    assert profile.options == {
        "post-remove-t": "true",
        "post-origin-before-m3": "false",
    }


def test_load_profiles_ignores_unknown_options(tmp_path: Path, caplog):
    caplog.set_level(logging.WARNING, logger="pcb2gcode_ui.profile_loader")
    (tmp_path / "Broken.yaml").write_text(
        """
description: Broken.
options:
  unknown-option: true
""",
        encoding="utf-8",
    )

    assert load_profiles(tmp_path) == ()
    assert "unknown option unknown-option" in caplog.text


def test_packaged_maxmake_profile_is_available():
    profiles = {profile.name: profile for profile in load_profiles()}

    profile = profiles["MaxMake"]
    assert profile.options["post-remove-t"] == "true"
    assert profile.options["post-origin-before-m3"] == "true"
    assert "tool probe is at least 15 mm" in profile.description
