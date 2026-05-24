import json
import logging
import os
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)
STATE_FILE_ENV_VAR = "PCB2GCODE_UI_STATE_FILE"
STATE_FILE_NAME = "state.json"
LAST_DIRECTORY_KEY = "last_directory"


def load_last_directory() -> Path:
    state_file = _state_file()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Path.cwd()
    except json.JSONDecodeError:
        LOGGER.warning("Ignoring invalid app state file %s", state_file)
        return Path.cwd()

    if not isinstance(data, dict):
        LOGGER.warning("Ignoring non-object app state file %s", state_file)
        return Path.cwd()

    path_value = data.get(LAST_DIRECTORY_KEY)
    if not isinstance(path_value, str):
        return Path.cwd()

    path = Path(path_value).expanduser()
    if not path.is_dir():
        LOGGER.debug("Ignoring missing last directory %s", path)
        return Path.cwd()
    return path


def save_last_directory(path: Path) -> None:
    state_file = _state_file()
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({LAST_DIRECTORY_KEY: str(path.expanduser())}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        LOGGER.exception("Failed to save app state to %s", state_file)


def _state_file() -> Path:
    configured_path = os.environ.get(STATE_FILE_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return _state_directory() / STATE_FILE_NAME


def _state_directory() -> Path:
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "pcb2gcode-ui"
        return Path.home() / "AppData" / "Roaming" / "pcb2gcode-ui"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "pcb2gcode-ui"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "pcb2gcode-ui"
    return Path.home() / ".config" / "pcb2gcode-ui"
