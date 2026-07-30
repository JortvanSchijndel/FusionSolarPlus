"""Helpers for sensor entity display names and translation keys."""

from __future__ import annotations

import re
from typing import Any


def normalize_display_key(name: str) -> str:
    """Convert a human-readable signal label into a stable translation key."""
    s = str(name)
    s = re.sub(r"\[Module \d+\]\s*", "module_", s, flags=re.IGNORECASE)
    s = re.sub(r"\[Battery [Pp]ack \d+\]\s*", "battery_pack_", s)
    s = re.sub(r"Battery [Pp]ack \d+\s*", "battery_pack_", s, flags=re.IGNORECASE)
    s = re.sub(r"\[PV \d+\]\s*", "pv_", s, flags=re.IGNORECASE)
    s1 = re.sub(r"(.)([A-Z][a-z0-9]+)", r"\1_\2", s)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return (
        s2.lower()
        .replace("-", "_")
        .replace(".", "_")
        .replace(" ", "_")
        .replace("__", "_")
        .strip("_")
    )


def pv_metric_translation_key(signal_id: int | str) -> str:
    """Map PV signal ids to shared metric translation keys."""
    offset = (int(signal_id) - 11001) % 3
    return ("pv_input_voltage", "pv_input_current", "pv_input_power")[offset]


PV_METRIC_LABELS = {
    "pv_input_voltage": "Input Voltage",
    "pv_input_current": "Input Current",
    "pv_input_power": "Input Power",
}


def entity_id_slug(name: str) -> str:
    """Build a stable entity_id slug from a human-readable signal name."""
    return str(name).lower().replace(" ", "_")


def signal_entity_id_name(
    signal: dict | None = None,
    *,
    display_name: str | None = None,
    api_name: str | None = None,
) -> str:
    """Resolve the stable display name used for entity_id generation."""
    if display_name:
        return display_name
    if signal:
        for key in ("display_name", "name"):
            value = signal.get(key)
            if value:
                return str(value)
    if api_name:
        return api_name
    if signal and signal.get("translation_key"):
        return str(signal["translation_key"])
    return "unknown"


def pv_api_name(pv_key: str, translation_key: str) -> str:
    """Build a PV entity display name when the API does not return one."""
    label = PV_METRIC_LABELS.get(translation_key, translation_key)
    return f"[{pv_key}] {label}"


def _clear_entity_attr(entity: Any, attr: str) -> None:
    """Remove an optional Entity attribute so HA falls back to defaults."""
    if hasattr(entity, attr):
        delattr(entity, attr)


def configure_sensor_names(
    entity: Any,
    *,
    translation_key: str,
    api_name: str | None = None,
    translation_placeholders: dict[str, str] | None = None,
    has_entity_name: bool = True,
) -> None:
    """Apply translation_key or API-provided name to a sensor entity."""
    entity._attr_has_entity_name = has_entity_name
    if api_name:
        entity._attr_name = api_name
        entity._attr_translation_key = None
        _clear_entity_attr(entity, "_attr_translation_placeholders")
    else:
        entity._attr_translation_key = translation_key
        if translation_placeholders:
            entity._attr_translation_placeholders = translation_placeholders
        else:
            # Do not set None; HA calls name.format(**placeholders) and None crashes.
            _clear_entity_attr(entity, "_attr_translation_placeholders")
        # Do not set _attr_name at all (even to None). Home Assistant checks
        # hasattr(_attr_name) before translation_key and None blocks i18n.
        _clear_entity_attr(entity, "_attr_name")


def extract_signal_names(raw_data: dict | None) -> dict[int, str]:
    """Build a signal-id to API name map from FusionSolar realtime payloads."""
    if not raw_data:
        return {}

    names: dict[int, str] = {}
    for group in raw_data.get("data", []):
        if not isinstance(group, dict):
            continue
        for signal in group.get("signals", []):
            signal_id = signal.get("id")
            name = signal.get("name")
            if signal_id is None or not name:
                continue
            try:
                names[int(signal_id)] = str(name)
            except (TypeError, ValueError):
                continue
    return names


def extract_signal_names_from_list(signals: list[dict] | None) -> dict[int, str]:
    """Build a signal-id to API name map from a flat signal list."""
    if not signals:
        return {}

    names: dict[int, str] = {}
    for signal in signals:
        signal_id = signal.get("id")
        name = signal.get("name")
        if signal_id is None or not name:
            continue
        try:
            names[int(signal_id)] = str(name)
        except (TypeError, ValueError):
            continue
    return names
