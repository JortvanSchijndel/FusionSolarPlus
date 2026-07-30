"""Charger API helpers."""

from __future__ import annotations

import time
import json
from typing import Any


def get_charger_data(client: Any, device_dn: str | None = None) -> dict:
    client.keep_alive()

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/pvms/organization/v1/tree"
    payload = {
        "parentDn": device_dn,
        "treeDepth": "device",
        "pageParam": {"needPage": True},
        "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
        "displayCond": {"self": False, "status": True},
    }
    r = client._session.post(url=url, json=payload)
    r.raise_for_status()
    response = r.json()
    dn_id_1 = response["childList"][0]["elementId"]

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details"
    params = (("dn", device_dn), ("_", round(time.time() * 1000)))
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    response = r.json()
    dn_id_2 = str(response.get("data", {}).get("mo", {}).get("dnId"))

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-realtime-info"
    payload = {
        "conditions": [
            {"dnId": dn_id_1, "queryAll": True},
            {"dnId": dn_id_2, "queryAll": True},
        ]
    }
    r = client._session.post(url=url, json=payload)
    r.raise_for_status()
    return _normalize_charger_payload(r.json())


def _normalize_charger_payload(raw_data: dict) -> dict:
    value_map: dict[tuple[str, int], Any] = {}
    for signal_type_id, signals_list in raw_data.items():
        if not isinstance(signals_list, list):
            continue
        for signal in signals_list:
            signal_id = signal.get("id")
            if signal_id is None:
                continue
            raw_value = signal.get("realValue", signal.get("value"))
            if raw_value in (None, "-", "N/A", "n/a"):
                value_map[(signal_type_id, int(signal_id))] = None
                continue
            try:
                value_map[(signal_type_id, int(signal_id))] = float(raw_value)
            except (TypeError, ValueError):
                value_map[(signal_type_id, int(signal_id))] = raw_value
    return {"raw_data": raw_data, "value_map": value_map}

def _resolve_parent_dn_id(client, device_dn: str) -> str:
    """Resolve the numeric dnId for the charger parent device."""
    client.keep_alive()
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details",
        params=(("dn", device_dn), ("_", round(time.time() * 1000))),
    )
    r.raise_for_status()
    try:
        return str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
    except Exception:
        from .exceptions import FusionSolarException
        raise FusionSolarException(
            f"Failed to parse mo-details for {device_dn}. Session may have expired."
        )


def _resolve_child_element_dn(client, device_dn: str) -> tuple[str, str]:
    """Resolve the charging pile child's elementId and elementDn.

    Returns (child_dn_id, child_element_dn), e.g. ("150468159", "NE=237145438").
    The elementDn must be used for set-signal on child signals.
    """
    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/pvms/organization/v1/tree",
        json={
            "parentDn": device_dn,
            "treeDepth": "device",
            "pageParam": {"needPage": True},
            "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
            "displayCond": {"self": False, "status": True},
        },
    )
    r.raise_for_status()
    children = r.json().get("childList", [])
    if not children:
        from ..exceptions import FusionSolarException
        raise FusionSolarException(f"No charging pile child found for {device_dn}")
    child = children[0]
    return str(child["elementId"]), child["elementDn"]


def get_charger_config(client, device_dn: str) -> dict:
    """Fetch config for both parent and charging pile child (get-config-info).

    Returns a combined dict keyed by dnId:
        {
            "150453477": [ ... parent signals ... ],  # Max Charge Power (id=20001)
            "150468159": [ ... child signals ...  ],  # Working Mode (id=20002)
        }
    """
    client.keep_alive()

    parent_dn_id = _resolve_parent_dn_id(client, device_dn)
    child_dn_id, _ = _resolve_child_element_dn(client, device_dn)

    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-config-info",
        json={
            "conditions": [
                {"dnId": parent_dn_id, "queryAll": True},
                {"dnId": child_dn_id, "queryAll": True},
            ]
        },
    )
    r.raise_for_status()
    return r.json()


def set_charger_max_charge_power(client, device_dn: str, max_power_kw: float) -> dict:
    """Set the max charge power limit on the charger parent (signal id=20001)."""
    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
        data={
            "dn": device_dn,
            "changeValues": json.dumps([{"id": "20001", "value": str(max_power_kw)}]),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json()


def set_charger_working_mode(client, device_dn: str, mode: str) -> dict:
    """Set the working mode on the charging pile child (signal id=20002).

    Resolves the elementDn dynamically — must use elementDn, NOT elementId.
    "0" = Normal charge, "1" = PV Power Preferred.
    The API returns code=-1 even on success for this device type.
    """
    mode = str(mode)
    if mode not in {"0", "1"}:
        raise ValueError(f"Invalid mode '{mode}'. Valid: 0=Normal charge, 1=PV Power Preferred")

    _, child_element_dn = _resolve_child_element_dn(client, device_dn)

    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
        data={
            "dn": child_element_dn,
            "changeValues": json.dumps([{"id": "20002", "value": mode}]),
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.json()


def charge_control(client, device_dn: str, action: str) -> dict:
    """Start or stop EV charging via the standard web API (port 443, no SSL issues).

    Endpoint: POST /rest/neteco/web/homemgr/v1/charger/charge/{start-charge|stop-charge}
    start-charge returns an empty body; stop-charge returns {"serialNumber": ""}.
    """
    action = action.lower()
    if action not in {"start", "stop"}:
        raise ValueError(f"Invalid action '{action}'. Valid: 'start' or 'stop'")

    client.keep_alive()
    parent_dn_id = int(_resolve_parent_dn_id(client, device_dn))
    endpoint = "start-charge" if action == "start" else "stop-charge"

    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/charger/charge/{endpoint}",
        json={
            "dnId": parent_dn_id,
            "gunNumber": 1,
            "orderNumber": None,
            "serialNumber": None,
        },
    )
    r.raise_for_status()
    return r.json() if r.text.strip() else {"success": True}
