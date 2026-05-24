from dataclasses import dataclass

from pcb2gcode_ui.options import OPTION_SPECS, SPEC_BY_KEY, bool_value
from pcb2gcode_ui.preprocess import (
    PRE_ALIGN_DRILL_DEPTH_KEY,
    PRE_ALIGN_DRILL_DIAMETER_KEY,
    PRE_ALIGN_DRILLS_KEY,
)


@dataclass(frozen=True)
class ValidationMessage:
    key: str
    text: str


def validate_values(values: dict[str, str]) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    for spec in OPTION_SPECS:
        value = values.get(spec.key, "").strip()
        if not value:
            continue
        if spec.kind == "bool":
            try:
                bool_value(value)
            except ValueError as error:
                messages.append(ValidationMessage(spec.key, str(error)))
        elif spec.kind == "choice" and value.lower() not in spec.choices:
            messages.append(
                ValidationMessage(spec.key, f"Expected one of: {', '.join(spec.choices)}")
            )
        elif spec.kind == "integer":
            _validate_integer(spec.key, value, messages)
        elif spec.kind == "number":
            _validate_number(spec.key, value, messages)

    _validate_required(values, messages)
    _validate_cross_fields(values, messages)
    return messages


def _validate_integer(key: str, value: str, messages: list[ValidationMessage]):
    try:
        int(value)
    except ValueError:
        messages.append(ValidationMessage(key, "Expected an integer."))


def _validate_number(key: str, value: str, messages: list[ValidationMessage]):
    if value.strip().lower() == "inf":
        return
    normalized = value.strip().rstrip("%")
    for suffix in ("in/min", "mm/min", "in", "mm", "ms", "s"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    try:
        float(normalized)
    except ValueError:
        messages.append(ValidationMessage(key, "Expected a number or pcb2gcode unit value."))


def _validate_required(values: dict[str, str], messages: list[ValidationMessage]):
    _require(values, messages, "zsafe")
    _require(values, messages, "zchange")
    if values.get("front", "").strip() or values.get("back", "").strip():
        for key in ("zwork", "mill-diameters", "mill-feed", "mill-speed"):
            _require(values, messages, key)
    if values.get("drill", "").strip():
        for key in ("zdrill", "drill-feed", "drill-speed"):
            _require(values, messages, key)
    if values.get("outline", "").strip() or values.get("min-milldrill-hole-diameter", "").strip():
        for key in ("zcut", "cutter-diameter", "cut-feed", "cut-speed", "cut-infeed"):
            _require(values, messages, key)
    if _enabled(values, "al-front") or _enabled(values, "al-back"):
        for key in ("software", "al-x", "al-y", "al-probefeed"):
            _require(values, messages, key)


def _validate_cross_fields(values: dict[str, str], messages: list[ValidationMessage]):
    if values.get("tolerance", "").strip() and values.get("g64", "").strip():
        messages.append(ValidationMessage("tolerance", "Cannot use tolerance and g64 together."))
    if values.get("mill-feed-direction", "any").strip().lower() != "any" and _enabled(
        values, "tsp-2opt"
    ):
        messages.append(
            ValidationMessage("mill-feed-direction", "Disable tsp-2opt for fixed feed direction.")
        )
    for key in ("tile-x", "tile-y"):
        value = values.get(key, "").strip()
        if value and value.isdigit() and int(value) < 1:
            messages.append(ValidationMessage(key, "Value must be at least 1."))
    if (
        _enabled(values, PRE_ALIGN_DRILLS_KEY)
        and values.get("outline", "").strip()
    ):
        _validate_required_positive_number(values, messages, PRE_ALIGN_DRILL_DIAMETER_KEY)
        _validate_required_non_zero_number(values, messages, PRE_ALIGN_DRILL_DEPTH_KEY)


def _require(values: dict[str, str], messages: list[ValidationMessage], key: str):
    if not values.get(key, "").strip():
        messages.append(ValidationMessage(key, f"{SPEC_BY_KEY[key].label} is required."))


def _validate_required_positive_number(
    values: dict[str, str],
    messages: list[ValidationMessage],
    key: str,
):
    value = _validate_required_number(values, messages, key)
    if value is not None and value <= 0:
        messages.append(ValidationMessage(key, "Value must be positive."))


def _validate_required_number(
    values: dict[str, str],
    messages: list[ValidationMessage],
    key: str,
) -> float | None:
    raw_value = values.get(key, "").strip()
    if not raw_value:
        messages.append(ValidationMessage(key, f"{SPEC_BY_KEY[key].label} is required."))
        return None
    value = _number_value(raw_value)
    if value is None and not any(message.key == key for message in messages):
        messages.append(ValidationMessage(key, "Expected a number or pcb2gcode unit value."))
    return value


def _validate_required_non_zero_number(
    values: dict[str, str],
    messages: list[ValidationMessage],
    key: str,
):
    value = _validate_required_number(values, messages, key)
    if value == 0:
        messages.append(ValidationMessage(key, "Value must be non-zero."))


def _number_value(value: str) -> float | None:
    normalized = value.strip().lower().rstrip("%")
    for suffix in ("in/min", "mm/min", "in", "mm", "ms", "s"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    try:
        return float(normalized)
    except ValueError:
        return None


def _enabled(values: dict[str, str], key: str) -> bool:
    try:
        return bool_value(values.get(key, "false"))
    except ValueError:
        return False
