import logging
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from pcb2gcode_ui.options import SPEC_BY_KEY

LOGGER = logging.getLogger(__name__)
PROFILE_PACKAGE = "pcb2gcode_ui.profiles"
PROFILE_SUFFIX = ".yaml"


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    options: Mapping[str, str]


def load_profiles(directory: Path = None) -> tuple[Profile, ...]:
    if directory:
        profile_paths = sorted(directory.glob(f"*{PROFILE_SUFFIX}"))
    else:
        profile_paths = sorted(
            item
            for item in files(PROFILE_PACKAGE).iterdir()
            if item.name.endswith(PROFILE_SUFFIX)
        )

    profiles = []
    for profile_path in profile_paths:
        profile = _load_profile(profile_path)
        if profile:
            profiles.append(profile)
    return tuple(profiles)


def _load_profile(profile_path: Traversable) -> Profile | None:
    profile_name = Path(profile_path.name).stem
    try:
        loaded_data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except OSError:
        LOGGER.exception("Failed to read profile %s", profile_path)
        return None
    except yaml.YAMLError:
        LOGGER.warning("Ignoring invalid YAML profile %s", profile_path, exc_info=True)
        return None

    if not isinstance(loaded_data, dict):
        LOGGER.warning("Ignoring profile %s: expected YAML object", profile_path)
        return None

    raw_options = loaded_data.get("options")
    if not isinstance(raw_options, dict):
        LOGGER.warning("Ignoring profile %s: expected options object", profile_path)
        return None

    option_values: dict[str, str] = {}
    for key, value in raw_options.items():
        if key not in SPEC_BY_KEY:
            LOGGER.warning("Ignoring profile %s: unknown option %s", profile_path, key)
            return None
        option_values[str(key)] = _profile_value(value)

    description = loaded_data.get("description", "")
    if not isinstance(description, str):
        LOGGER.warning("Ignoring profile %s: expected description text", profile_path)
        return None

    return Profile(
        name=profile_name,
        description=description,
        options=MappingProxyType(option_values),
    )


def _profile_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
