"""Power sensor API helpers."""

from __future__ import annotations

from typing import Any

from custom_components.fusionsolarplus.api.devices import inverter_api


def get_powersensor_data(client: Any, device_dn: str | None = None) -> dict:
    raw_data = inverter_api.get_real_time_data(client, device_dn)
    value_map: dict[int, Any] = {}
    all_signal_ids: set[int] = set()

    for signal in _iter_signals(raw_data):
        signal_id = signal.get("id")
        if signal_id is None:
            continue
        try:
            signal_id = int(signal_id)
        except (TypeError, ValueError):
            continue
        all_signal_ids.add(signal_id)
        raw_value = signal.get("realValue", signal.get("value"))
        if raw_value in (None, "-", "N/A", "n/a"):
            value_map[signal_id] = None
            continue
        if signal.get("unit"):
            try:
                value_map[signal_id] = float(raw_value)
            except (TypeError, ValueError):
                value_map[signal_id] = None
        else:
            value_map[signal_id] = raw_value

    model = "Unknown"
    if 230700283 in all_signal_ids:
        model = "Emma A02"
    elif 10001 in all_signal_ids:
        model = "Standard"
    elif 2101249 in all_signal_ids:
        model = "DTSU666-FE"

    return {"raw_data": raw_data, "value_map": value_map, "model": model}


def _iter_signals(data: dict):
    if not data:
        return
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        for group in data.get("data", []):
            if isinstance(group, dict) and isinstance(group.get("signals"), list):
                for signal in group["signals"]:
                    yield signal
            elif isinstance(group, list):
                for signal in group:
                    yield signal
        return
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                for signal in value:
                    yield signal
