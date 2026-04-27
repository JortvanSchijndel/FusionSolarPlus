"""Inverter API helpers.

This module contains all inverter-related HTTP calls and payload normalization.
The goal is to keep Home Assistant entity classes thin: sensors should only read
pre-normalized values from the coordinator payload instead of parsing raw API data.
"""

from __future__ import annotations

import re
import time
from typing import Any

from custom_components.fusionsolarplus.api.exceptions import FusionSolarException


def get_historical_data(
    client: Any,
    signal_ids: list[str],
    device_dn: str | None = None,
    date=None,
) -> dict:
    if date is None:
        date = time.localtime()
        timestamp_ms = int(time.mktime(date) * 1000)
    else:
        timestamp_ms = int(date.timestamp() * 1000)

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-history-data"
    params = ()
    for signal_id in signal_ids:
        params += (("signalIds", signal_id),)
    params += (
        ("deviceDn", device_dn),
        ("date", timestamp_ms),
        ("_", round(time.time() * 1000)),
    )
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    return r.json(parse_float=client._parse_float)


def get_real_time_data(client: Any, device_dn: str | None = None) -> dict:
    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-realtime-data"
    params = (("deviceDn", device_dn), ("_", round(time.time() * 1000)))
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    return r.json()


def get_inverter_data(client: Any, device_dn: str) -> dict:
    """Fetch and normalize all inverter datasets used by Home Assistant."""
    realtime_data = get_real_time_data(client, device_dn)
    pv_data = get_pv_info(client, device_dn)
    optimizer_data = get_optimizer_stats(client, device_dn)
    return {
        "raw_realtime_data": realtime_data,
        "raw_pv_data": pv_data,
        "raw_optimizer_data": optimizer_data,
        "inverter_values": _extract_inverter_values(realtime_data),
        "pv_values": _extract_pv_values(pv_data),
        "optimizer_values": _extract_optimizer_values(optimizer_data),
    }


def get_pv_info(client: Any, device_dn: str | None = None) -> dict:
    avail_url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-statistics-signal"
    avail_params = {"deviceDn": device_dn, "_": round(time.time() * 1000)}
    r_avail = client._session.get(url=avail_url, params=avail_params)
    r_avail.raise_for_status()
    avail_data = r_avail.json()

    available_pvs = []
    for signal in avail_data.get("data", {}).get("signalList", []):
        name = signal.get("name", "")
        match = re.search(r"\bPV\d+\b", name)
        if match:
            pv_id = match.group(0)
            if pv_id not in available_pvs:
                available_pvs.append(pv_id)

    pv_signal_map = {
        "PV1": [("11001", "11002", "11003")],
        "PV2": [("11004", "11005", "11006")],
        "PV3": [("11007", "11008", "11009")],
        "PV4": [("11010", "11011", "11012")],
        "PV5": [("11013", "11014", "11015")],
        "PV6": [("11016", "11017", "11018")],
        "PV7": [("11019", "11020", "11021")],
        "PV8": [("11022", "11023", "11024")],
        "PV9": [("11025", "11026", "11027")],
        "PV10": [("11028", "11029", "11030")],
        "PV11": [("11031", "11032", "11033")],
        "PV12": [("11034", "11035", "11036")],
        "PV13": [("11037", "11038", "11039")],
        "PV14": [("11040", "11041", "11042")],
        "PV15": [("11043", "11044", "11045")],
        "PV16": [("11046", "11047", "11048")],
        "PV17": [("11049", "11050", "11051")],
        "PV18": [("11052", "11053", "11054")],
        "PV19": [("11055", "11056", "11057")],
        "PV20": [("11058", "11059", "11060")],
    }

    signal_ids = []
    for pv in available_pvs:
        pairs = pv_signal_map.get(pv)
        if pairs:
            for voltage_id, current_id, _ in pairs:
                signal_ids.extend([voltage_id, current_id])

    params = [("signalIds", sid) for sid in signal_ids]
    params.append(("deviceDn", device_dn))
    params.append(("_", round(time.time() * 1000)))

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-real-kpi"
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    data = r.json()
    signals = data.get("data", {}).get("signals", {})

    latest_time = int(time.time())
    for pv in available_pvs:
        pairs = pv_signal_map.get(pv)
        if pairs:
            for voltage_id, current_id, power_id in pairs:
                val1 = signals.get(voltage_id, {}).get("realValue")
                val2 = signals.get(current_id, {}).get("realValue")
                try:
                    product = float(val1) * float(val2)
                    signals[power_id] = {
                        "value": f"{product:.2f}",
                        "realValue": f"{product:.2f}",
                        "latestTime": latest_time,
                    }
                except (TypeError, ValueError):
                    continue

    filtered_signals = {}
    for pv in available_pvs:
        pairs = pv_signal_map.get(pv)
        if pairs:
            for voltage_id, current_id, power_id in pairs:
                for sid in (voltage_id, current_id, power_id):
                    if sid in signals:
                        filtered_signals[sid] = signals[sid]

    if not filtered_signals:
        latest_time = int(time.time())
        for pv in available_pvs:
            pairs = pv_signal_map.get(pv)
            if pairs:
                for voltage_id, current_id, power_id in pairs:
                    for sid in (voltage_id, current_id, power_id):
                        filtered_signals[sid] = {
                            "value": "0.00",
                            "realValue": "0.00",
                            "latestTime": latest_time,
                        }

    return {"signals": filtered_signals, "available_pvs": available_pvs}


def get_optimizer_stats(client: Any, inverter_id: str):
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/layout/optimizer-info",
        params={"inverterDn": inverter_id, "_": round(time.time() * 1000)},
    )
    r.raise_for_status()
    optimizer_data = r.json()
    if "exceptionType" in optimizer_data:
        return []
    if not optimizer_data["success"] or "data" not in optimizer_data:
        raise FusionSolarException(f"Failed to retrieve plant status for {inverter_id}")
    return optimizer_data["data"]


def _extract_inverter_values(realtime_data: dict) -> dict[int, Any]:
    values: dict[int, Any] = {}
    for group in realtime_data.get("data", []):
        for signal in group.get("signals", []):
            signal_id = signal.get("id")
            if signal_id is None:
                continue
            raw_value = signal.get("value")
            values[int(signal_id)] = _normalize_signal_value(
                raw_value, signal.get("unit"), signal.get("name")
            )
    return values


def _extract_pv_values(pv_data: dict) -> dict[int, Any]:
    values: dict[int, Any] = {}
    for signal_id, signal_data in pv_data.get("signals", {}).items():
        raw_value = signal_data.get("value")
        try:
            key = int(signal_id)
        except (TypeError, ValueError):
            continue
        values[key] = _normalize_signal_value(raw_value, signal_data.get("unit"))
    return values


def _extract_optimizer_values(optimizer_data: list[dict]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for optimizer in optimizer_data:
        optimizer_name = optimizer.get("optName", "Optimizer")
        normalized_metrics: dict[str, Any] = {}
        for metric_name, metric_value in optimizer.items():
            if metric_name == "optName":
                continue
            normalized_metrics[metric_name] = _normalize_signal_value(
                metric_value, None
            )
        values[optimizer_name] = normalized_metrics
    return values


def _normalize_signal_value(
    raw_value: Any, unit: Any, signal_name: str | None = None
) -> Any:
    if raw_value in ("N/A", "n/a", None):
        return None

    if raw_value == "-":
        # Special handling for status signals
        if signal_name and signal_name.lower().startswith("status"):
            return "Inverter is Shutdown"
        return None

    if unit not in (None, ""):
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    return raw_value
