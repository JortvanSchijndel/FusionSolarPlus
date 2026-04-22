"""BackupBox API helpers."""

from __future__ import annotations

from typing import Any

from custom_components.fusionsolarplus.api.devices import inverter_api


def get_backupbox_data(client: Any, device_dn: str | None = None) -> dict:
    raw_data = inverter_api.get_real_time_data(client, device_dn)
    value_map: dict[int, Any] = {}
    for group in raw_data.get("data", []):
        for signal in group.get("signals", []):
            signal_id = signal.get("id")
            if signal_id is None:
                continue
            raw_value = signal.get("value", signal.get("realValue"))
            if raw_value in (None, "-", "N/A", "n/a"):
                value_map[int(signal_id)] = None
                continue
            try:
                value_map[int(signal_id)] = float(raw_value)
            except (TypeError, ValueError):
                value_map[int(signal_id)] = str(raw_value)
    return {"raw_data": raw_data, "value_map": value_map}
