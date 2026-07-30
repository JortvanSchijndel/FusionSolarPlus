"""EMMA API helpers.

Realtime values come from device-realtime-data on every poll.
Configuration (peak shaving, working mode, feed-in limits, …) comes from
deviceExt/get-config-signals and is cached per device DN (see EMMA_CONFIG_CACHE_TTL).
"""

from __future__ import annotations

import base64
import html
import json
import logging
import struct
import time
from typing import Any

from custom_components.fusionsolarplus.api.devices import inverter_api

_LOGGER = logging.getLogger(__name__)

# Config parameters change rarely (manual edits in FusionSolar). Realtime stays on
# the coordinator interval (~15s); config is refreshed at most every 5 minutes.
EMMA_CONFIG_CACHE_TTL = 300

SIGNAL_PEAK_POWER_SETTING = 230700179

# Fallback labels when the API response has no enumList for a signal.
_ENUM_FALLBACKS: dict[int, dict[str, str]] = {
    230700177: {
        "0": "No control",
        "1": "Active power limit",
        "2": "Apparent power limit",
    },
    21021: {
        "2": "Maximum self-consumption",
        "4": "Fully fed to grid",
        "5": "TOU",
        "7": "Third-party dispatch",
    },
    230700278: {"0": "Disable", "1": "Enable"},
    21115: {
        "0": "Unlimited",
        "5": "Zero Export Limitation",
        "6": "Limited Power Grid(kW)",
        "7": "Limited Power Grid(%)",
    },
    230700180: {"0": "Battery first", "1": "Appliances first"},
}

# module-level cache: device_dn -> {updated_at, config_map, peak_periods}
_config_cache: dict[str, dict[str, Any]] = {}


def get_emma_data(client: Any, device_dn: str | None = None) -> dict:
    """Fetch realtime EMMA data and (throttled) configuration signals."""
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

    config = _get_config_cached(client, device_dn)
    return {
        "raw_data": raw_data,
        "value_map": value_map,
        "config_map": config["config_map"],
        "peak_periods": config["peak_periods"],
        "config_updated_at": config["updated_at"],
    }


def get_config_signals(client: Any, device_dn: str | None = None) -> dict:
    """Fetch and normalize EMMA configuration signals (uncached)."""
    raw = _fetch_config_signals(client, device_dn)
    config_map, peak_periods = _normalize_config_signals(raw)
    return {
        "config_map": config_map,
        "peak_periods": peak_periods,
        "raw": raw,
    }


def decode_peak_power_setting(raw: str | None) -> list[dict[str, Any]]:
    """Decode Maximum peak power setting (signal 230700179).

    Supports two FusionSolar encodings seen in the wild:

    1. HTML-escaped JSON (typical ``get-config-signals`` response)::

         [{&quot;endTime&quot;:&quot;23:59&quot;,&quot;maxPeakPower&quot;:&quot;1.700&quot;,
           &quot;repeatPeriod&quot;:[7,1,2,3,4,5,6],&quot;startTime&quot;:&quot;00:00&quot;}]

    2. Base64 binary (128 bytes), capture example::

         AAEAAAWfAAAGpH8... -> one period 00:00-23:59 at 1.700 kW (everyday)

    Returns a list of period dicts::

        [{"start": "00:00", "end": "23:59", "peak_power_kw": 1.7, "repeat": "everyday"}]
    """
    if raw is None or raw == "" or raw in ("-", "N/A", "n/a"):
        return []

    text = html.unescape(str(raw)).strip()
    if text.startswith("["):
        return _decode_peak_power_json(text)

    return _decode_peak_power_base64(text)


def current_peak_power_kw(periods: list[dict[str, Any]]) -> float | None:
    """Return peak power (kW) for the period active now, else the first period."""
    if not periods:
        return None
    active = _active_period(periods)
    if active is not None:
        return active.get("peak_power_kw")
    return periods[0].get("peak_power_kw")


def _get_config_cached(client: Any, device_dn: str | None) -> dict[str, Any]:
    cache_key = device_dn or ""
    now = time.time()
    cached = _config_cache.get(cache_key)

    if cached and (now - cached["updated_at"]) < EMMA_CONFIG_CACHE_TTL:
        return {
            "config_map": cached["config_map"],
            "peak_periods": cached["peak_periods"],
            "updated_at": cached["updated_at"],
        }

    try:
        result = get_config_signals(client, device_dn)
        entry = {
            "updated_at": now,
            "config_map": result["config_map"],
            "peak_periods": result["peak_periods"],
        }
        _config_cache[cache_key] = entry
        return {
            "config_map": entry["config_map"],
            "peak_periods": entry["peak_periods"],
            "updated_at": entry["updated_at"],
        }
    except Exception:
        _LOGGER.debug(
            "EMMA config-signals fetch failed for %s; keeping stale cache if any",
            device_dn,
            exc_info=True,
        )
        if cached:
            return {
                "config_map": cached["config_map"],
                "peak_periods": cached["peak_periods"],
                "updated_at": cached["updated_at"],
            }
        return {"config_map": {}, "peak_periods": [], "updated_at": None}


def _fetch_config_signals(client: Any, device_dn: str | None) -> dict:
    url = (
        f"https://{client._huawei_subdomain}.fusionsolar.huawei.com"
        f"/rest/pvms/web/device/v1/deviceExt/get-config-signals"
    )
    params = {"dn": device_dn, "_": round(time.time() * 1000)}
    response = client._session.get(url=url, params=params)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0", None) and "data" not in payload:
        raise RuntimeError(
            f"get-config-signals failed for {device_dn}: {payload.get('description')}"
        )
    return payload


def _normalize_config_signals(
    raw: dict,
) -> tuple[dict[int, Any], list[dict[str, Any]]]:
    config_map: dict[int, Any] = {}
    peak_periods: list[dict[str, Any]] = []

    for signal in _iter_config_signals(raw):
        signal_id = signal.get("id")
        if signal_id is None:
            continue
        sid = int(signal_id)
        value = signal.get("value")
        if value in (None, "-", "N/A", "n/a", ""):
            config_map[sid] = None
            continue

        if sid == SIGNAL_PEAK_POWER_SETTING:
            peak_periods = decode_peak_power_setting(str(value))
            # Store current peak power (kW) for simple map lookups.
            config_map[sid] = current_peak_power_kw(peak_periods)
            continue

        data_type = (signal.get("dataType") or "").upper()
        has_api_enum = bool(signal.get("enumList") or signal.get("enumListEntry"))
        enum_list = _build_enum_map(signal, sid)

        if data_type == "ENUM" or has_api_enum:
            key = str(value)
            label = enum_list.get(key)
            if label is None:
                label = _ENUM_FALLBACKS.get(sid, {}).get(key, key)
            config_map[sid] = html.unescape(str(label))
            continue

        if data_type in ("FLOAT", "DOUBLE") or (
            data_type not in ("INT", "LONG", "ENUM", "STRING", "BASE64")
            and _looks_numeric(value)
            and "." in str(value)
        ):
            try:
                config_map[sid] = float(value)
                continue
            except (TypeError, ValueError):
                pass

        if data_type in ("INT", "LONG") or _looks_numeric(value):
            try:
                number = float(value)
                config_map[sid] = int(number) if number.is_integer() else number
                continue
            except (TypeError, ValueError):
                pass

        config_map[sid] = html.unescape(str(value))

    return config_map, peak_periods


def _iter_config_signals(raw: dict):
    data = raw.get("data", [])
    if not isinstance(data, list):
        return
    for group in data:
        if not isinstance(group, dict):
            continue
        signals = group.get("configSignalDisplayList") or group.get("signals") or []
        if not isinstance(signals, list):
            continue
        for signal in signals:
            if isinstance(signal, dict):
                yield signal


def _build_enum_map(signal: dict, signal_id: int) -> dict[str, str]:
    enum_list = signal.get("enumList")
    result: dict[str, str] = {}
    if isinstance(enum_list, dict):
        for key, label in enum_list.items():
            result[str(key)] = html.unescape(str(label))
    entries = signal.get("enumListEntry")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                for key, label in entry.items():
                    result[str(key)] = html.unescape(str(label))
    if not result:
        result = {
            key: html.unescape(label)
            for key, label in _ENUM_FALLBACKS.get(signal_id, {}).items()
        }
    return result


def _looks_numeric(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _decode_peak_power_json(text: str) -> list[dict[str, Any]]:
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        _LOGGER.debug("Failed to parse peak power JSON: %s", text[:120])
        return []

    periods: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return periods
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("startTime") or item.get("start") or "00:00"
        end = item.get("endTime") or item.get("end") or "23:59"
        power_raw = item.get("maxPeakPower") or item.get("peak_power_kw") or item.get(
            "peakPower"
        )
        try:
            peak_power_kw = float(power_raw)
        except (TypeError, ValueError):
            continue
        repeat = _repeat_label(item.get("repeatPeriod"))
        periods.append(
            {
                "start": str(start),
                "end": str(end),
                "peak_power_kw": peak_power_kw,
                "repeat": repeat,
            }
        )
    return periods


def _decode_peak_power_base64(text: str) -> list[dict[str, Any]]:
    """Decode Base64 packed periods.

    Layout (big-endian), verified against capture AAEAAAWfAAAGpH8...:
      uint16 count
      per period (10 bytes): start_min, end_min, reserved, power_w, days_be
      days high byte 0x7F => everyday (bits for Mon-Sun).
    """
    try:
        data = base64.b64decode(text, validate=False)
    except Exception:
        _LOGGER.debug("Failed to base64-decode peak power setting")
        return []

    if len(data) < 2:
        return []

    count = struct.unpack_from(">H", data, 0)[0]
    if count <= 0 or count > 14:
        return []

    periods: list[dict[str, Any]] = []
    offset = 2
    for _ in range(count):
        if offset + 10 > len(data):
            break
        start_min, end_min, _reserved, power_w, days = struct.unpack_from(
            ">HHHHH", data, offset
        )
        offset += 10
        periods.append(
            {
                "start": _minutes_to_hhmm(start_min),
                "end": _minutes_to_hhmm(end_min),
                "peak_power_kw": round(power_w / 1000.0, 3),
                "repeat": _repeat_from_days_mask(days),
            }
        )
    return periods


def _minutes_to_hhmm(minutes: int) -> str:
    minutes = max(0, min(int(minutes), 24 * 60 - 1))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _hhmm_to_minutes(value: str) -> int | None:
    try:
        hours, mins = value.split(":")
        return int(hours) * 60 + int(mins)
    except (TypeError, ValueError, AttributeError):
        return None


def _repeat_label(repeat_period: Any) -> str:
    if not isinstance(repeat_period, list) or not repeat_period:
        return "unknown"
    days = sorted({int(day) for day in repeat_period if str(day).isdigit()})
    if days == [1, 2, 3, 4, 5, 6, 7] or days == [7, 1, 2, 3, 4, 5, 6]:
        return "everyday"
    if set(days) == {1, 2, 3, 4, 5}:
        return "weekdays"
    if set(days) == {6, 7}:
        return "weekend"
    return ",".join(str(day) for day in days)


def _repeat_from_days_mask(days_be: int) -> str:
    # High byte holds weekday bits in the captured payload (0x7F00 => everyday).
    mask = (days_be >> 8) & 0xFF
    if mask == 0:
        mask = days_be & 0xFF
    if mask == 0x7F:
        return "everyday"
    return f"mask:{mask:02x}"


def _active_period(periods: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = time.localtime()
    now_min = now.tm_hour * 60 + now.tm_min
    for period in periods:
        start = _hhmm_to_minutes(period.get("start", ""))
        end = _hhmm_to_minutes(period.get("end", ""))
        if start is None or end is None:
            continue
        if start <= end:
            if start <= now_min <= end:
                return period
        else:
            # Overnight window
            if now_min >= start or now_min <= end:
                return period
    return None
