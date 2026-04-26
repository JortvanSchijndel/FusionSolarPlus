"""Battery API helpers."""

from __future__ import annotations

import logging
import time
from typing import Any

from custom_components.fusionsolarplus.api.constants import MODULE_SIGNALS
from custom_components.fusionsolarplus.api.exceptions import FusionSolarException


def get_battery_ids(client: Any, plant_id) -> list:
    plant_flow = client.get_plant_flow(plant_id)
    nodes = plant_flow["data"]["flow"]["nodes"]
    battery_ids = []

    for node in nodes:
        name = node.get("name", "")
        dev_ids = node.get("devIds")
        logging.debug("Processing node: name=%r devIds=%r", name, dev_ids)
        if "energy_store" in name:
            if isinstance(dev_ids, list) and dev_ids:
                battery_ids.extend(dev_ids)
            else:
                logging.warning(
                    "Node with 'energy_store' in name but devIds is not a non-empty list: %r",
                    node,
                )
    return battery_ids


def get_battery_day_stats(
    client: Any, battery_id: str, query_time: int | None = None
) -> dict:
    current_time = round(time.time() * 1000)
    if query_time is not None:
        current_time = query_time
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-history-data",
        params={
            "signalIds": ["30005", "30007"],
            "deviceDn": battery_id,
            "date": current_time,
            "_": current_time,
        },
    )
    r.raise_for_status()
    battery_data = r.json()
    if not battery_data["success"] or "data" not in battery_data:
        raise FusionSolarException(
            f"Failed to retrieve battery day stats for {battery_id}"
        )
    battery_data["data"]["30005"]["name"] = "Charge/Discharge power"
    battery_data["data"]["30007"]["name"] = "SOC"
    return battery_data["data"]


def get_battery_module_stats(
    client: Any, battery_id: str, module_id: str = "1", signal_ids: list | None = None
) -> dict:
    if signal_ids is None:
        signal_ids = MODULE_SIGNALS[module_id]
    elif not all(signal_id in MODULE_SIGNALS[module_id] for signal_id in signal_ids):
        raise ValueError(f"One or more unknown signal ids for module {module_id}")

    signal_ids_str = ",".join(signal_ids)
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/query-battery-dc",
        params={
            "sigids": signal_ids_str,
            "dn": battery_id,
            "moduleId": module_id,
            "_": round(time.time() * 1000),
        },
    )
    r.raise_for_status()
    battery_data = r.json()
    if not battery_data["success"] or "data" not in battery_data:
        raise FusionSolarException(
            f"Failed to retrieve battery status for {battery_id}"
        )
    return battery_data["data"]


def get_battery_status(client: Any, battery_id: str) -> dict:
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-realtime-data",
        params={"deviceDn": battery_id, "_": round(time.time() * 1000)},
    )
    r.raise_for_status()
    battery_data = r.json()
    if not battery_data["success"] or "data" not in battery_data:
        raise FusionSolarException(
            f"Failed to retrieve battery status for {battery_id}"
        )
    return battery_data["data"][1]["signals"]


def get_battery_data(client: Any, battery_id: str) -> dict:
    """Fetch and normalize battery status plus module-level values."""
    battery_signals = get_battery_status(client, battery_id)
    modules: dict[str, list[dict]] = {}
    module_values: dict[str, dict[int, Any]] = {}
    for module_id in ["1", "2", "3", "4"]:
        module_signals = get_battery_module_stats(client, battery_id, module_id)
        modules[module_id] = module_signals
        module_values[module_id] = _signals_to_value_map(module_signals)

    return {
        "battery": battery_signals,
        "modules": modules,
        "battery_values": _signals_to_value_map(battery_signals, "value"),
        "module_values": {
            module_id: _signals_to_value_map(modules[module_id], "realValue")
            for module_id in modules
        },
    }


def _signals_to_value_map(
    signals: list[dict], value_key: str = "value"
) -> dict[int, Any]:
    values: dict[int, Any] = {}
    for signal in signals:
        signal_id = signal.get("id")
        if signal_id is None:
            continue

        raw_value = signal.get(value_key)

        if raw_value in (None, "-", "N/A", "n/a"):
            values[int(signal_id)] = None
            continue

        try:
            values[int(signal_id)] = float(raw_value)
        except (TypeError, ValueError):
            values[int(signal_id)] = raw_value

    return values
