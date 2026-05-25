import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)
STATE_FILE_ENV_VAR = "PCB2GCODE_UI_STATE_FILE"
STATE_FILE_NAME = "state.json"
LAST_DIRECTORY_KEY = "last_directory"
DEFAULT_MILLPROJECT_KEY = "default_millproject"
SELECTED_PROFILE_KEY = "selected_profile"


@dataclass(frozen=True)
class AppSettings:
    last_directory: Path
    default_millproject: Path = None
    selected_profile: str = ""


def load_last_directory() -> Path:
    return load_app_settings().last_directory


def save_last_directory(path: Path) -> None:
    settings = load_app_settings()
    save_app_settings(
        AppSettings(
            last_directory=path,
            default_millproject=settings.default_millproject,
            selected_profile=settings.selected_profile,
        )
    )


def load_app_settings() -> AppSettings:
    state_file = _state_file()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppSettings(last_directory=Path.cwd())
    except json.JSONDecodeError:
        LOGGER.warning("Ignoring invalid app state file %s", state_file)
        return AppSettings(last_directory=Path.cwd())

    if not isinstance(data, dict):
        LOGGER.warning("Ignoring non-object app state file %s", state_file)
        return AppSettings(last_directory=Path.cwd())

    return AppSettings(
        last_directory=_load_directory(data),
        default_millproject=_load_default_millproject(data),
        selected_profile=_load_selected_profile(data),
    )


def save_app_settings(settings: AppSettings) -> None:
    state_file = _state_file()
    data = {LAST_DIRECTORY_KEY: str(settings.last_directory.expanduser())}
    if settings.default_millproject:
        data[DEFAULT_MILLPROJECT_KEY] = str(settings.default_millproject.expanduser())
    if settings.selected_profile:
        data[SELECTED_PROFILE_KEY] = settings.selected_profile

    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        LOGGER.exception("Failed to save app state to %s", state_file)


def _load_directory(data: dict) -> Path:
    path_value = data.get(LAST_DIRECTORY_KEY)
    if not isinstance(path_value, str):
        return Path.cwd()

    path = Path(path_value).expanduser()
    if not path.is_dir():
        LOGGER.debug("Ignoring missing last directory %s", path)
        return Path.cwd()
    return path


def _load_default_millproject(data: dict) -> Path:
    path_value = data.get(DEFAULT_MILLPROJECT_KEY)
    if not isinstance(path_value, str):
        return None

    path = Path(path_value).expanduser()
    if not path.is_file():
        LOGGER.debug("Ignoring missing default millproject %s", path)
        return None
    return path


def _load_selected_profile(data: dict) -> str:
    profile_name = data.get(SELECTED_PROFILE_KEY)
    if not isinstance(profile_name, str):
        return ""
    return profile_name


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
