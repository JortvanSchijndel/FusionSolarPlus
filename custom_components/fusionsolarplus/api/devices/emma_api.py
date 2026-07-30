"""EMMA API helpers."""

from __future__ import annotations

from typing import Any

from custom_components.fusionsolarplus.api.devices import inverter_api

import json
import time

def get_emma_data(client: Any, device_dn: str | None = None) -> dict:
    raw_data = inverter_api.get_real_time_data(client, device_dn)
    value_map: dict[int, Any] = {}
    for group in raw_data.get("data", []):
        for signal in group.get("signals", []):
            signal_id = signal.get("id")
            if signal_id is None:
                continue
            raw_value = signal.get("realValue", signal.get("value"))
            if raw_value in (None, "-", "N/A", "n/a"):
                value_map[int(signal_id)] = None
                continue
            try:
                value_map[int(signal_id)] = float(raw_value)
            except (TypeError, ValueError):
                value_map[int(signal_id)] = str(raw_value)
    return {"raw_data": raw_data, "value_map": value_map}

def get_smart_assistant_config(client, device_dn: str) -> dict:
    """Fetch SmartAssistant config signals (get-config-info).

    Returns a dict keyed by dnId, including PV Power Priority (signal id=230700180):
        "0" = Battery first, "1" = Appliances first
    """
    client.keep_alive()

    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details",
        params=(("dn", device_dn), ("_", round(time.time() * 1000))),
    )
    r.raise_for_status()
    try:
        dn_id = str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
    except Exception:
        from ..exceptions import FusionSolarException
        raise FusionSolarException(
            f"Failed to parse mo-details for {device_dn}. Session may have expired."
        )

    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-config-info",
        json={"conditions": [{"dnId": dn_id, "queryAll": True}]},
    )
    r.raise_for_status()
    return r.json()


def set_smart_assistant_pv_priority(client, device_dn: str, priority: str) -> dict:
    """Set the PV Power Priority on the SmartAssistant (signal id=230700180).

    "0" = Battery first, "1" = Appliances first
    """
    priority = str(priority)
    if priority not in {"0", "1"}:
        raise ValueError(
            f"Invalid priority '{priority}'. Valid: 0=Battery first, 1=Appliances first"
        )

    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
        data={
            "dn": device_dn,
            "changeValues": json.dumps([{"id": "230700180", "value": priority}]),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json()
