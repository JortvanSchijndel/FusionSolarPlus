"""Plant API helpers."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from custom_components.fusionsolarplus.api.exceptions import FusionSolarException


def get_current_plant_data(client: Any, plant_id: str) -> dict:
    """Retrieve current plant KPI and energy flow data."""
    ts = round(time.time() * 1000)

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/station-real-kpi"
    params = {
        "stationDn": plant_id,
        "clientTime": ts,
        "timeZone": 1,
        "_": ts,
    }
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    power_obj = r.json()

    if "data" not in power_obj:
        raise FusionSolarException("Failed to retrieve plant KPI data.")

    today = datetime.now(timezone.utc).astimezone()
    query_time = int(
        today.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
    )
    date_str = today.strftime("%Y-%m-%d 00:00:00")

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v3/overview/energy-balance"
    params = {
        "stationDn": plant_id,
        "timeDim": 2,
        "timeZone": 1.0,
        "timeZoneStr": today.tzname(),
        "queryTime": query_time,
        "dateStr": date_str,
        "_": ts,
    }
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    energy_obj = r.json()

    if "data" not in energy_obj:
        raise FusionSolarException("Failed to retrieve plant energy balance data.")

    data = power_obj["data"]
    energy = energy_obj["data"]

    url = f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v3/overview/energy-flow"
    params = {"stationDn": plant_id, "featureId": "aifc", "_": ts}
    r = client._session.get(url=url, params=params)
    r.raise_for_status()
    flow_data = r.json()

    if "data" in flow_data and "flow" in flow_data["data"]:
        flow = flow_data["data"]["flow"]
        nodes = flow.get("nodes", [])
        links = flow.get("links", [])

        def get_node_value(name: str):
            for node in nodes:
                if node.get("name") == name:
                    return node.get("value")
            return None

        data["flow_solar_power"] = get_node_value("neteco.pvms.devTypeLangKey.string")
        data["flow_battery_power"] = get_node_value(
            "neteco.pvms.devTypeLangKey.energy_store"
        )
        data["flow_load_power"] = get_node_value(
            "neteco.pvms.KPI.kpiView.electricalLoad"
        )

        grid_id = next(
            (
                n["id"]
                for n in nodes
                if n.get("name")
                == "neteco.pvms.partials.main.dm.detailInfo.curInfo.grid"
            ),
            None,
        )
        meter_id = next(
            (
                n["id"]
                for n in nodes
                if n.get("name") == "neteco.pvms.devTypeLangKey.meter"
            ),
            None,
        )

        if grid_id and meter_id:
            for link in links:
                if link.get("fromNode") == grid_id and link.get("toNode") == meter_id:
                    desc = link.get("description", {})
                    val_str = desc.get("value")
                    if val_str and " " in val_str:
                        try:
                            data["flow_grid_power"] = float(val_str.split(" ")[0])
                        except ValueError:
                            pass
                    break

    data.update(
        {
            "existMeter": energy.get("existMeter", False),
            "existInverter": energy.get("existInverter", True),
            "totalSelfUseEnergy": energy.get("totalSelfUsePower"),
            "totalFeedInEnergy": energy.get("totalOnGridPower"),
            "totalGridImportEnergy": energy.get("totalBuyPower"),
            "totalConsumptionEnergy": energy.get("totalUsePower"),
            "pvSelfConsumptionEnergy": energy.get("selfProvide"),
            "gridImportRatio": energy.get("buyPowerRatio"),
            "pvSelfConsumptionRatio": energy.get("selfUsePowerRatioByUse"),
            "pvSelfConsumptionRatioByProduction": energy.get(
                "selfUsePowerRatioByProduct"
            ),
        }
    )

    for key, value in list(data.items()):
        if key.startswith("exist"):
            data[key] = bool(value)
            continue
        if value in (None, "-", "N/A", "n/a"):
            data[key] = None
            continue
        try:
            data[key] = float(value)
        except (TypeError, ValueError):
            data[key] = value

    return data


def get_plant_ids(client: Any) -> list:
    station_list = get_station_list(client)
    return [obj["dn"] for obj in station_list]


def get_station_list(client: Any) -> list:
    r = client._session.post(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/station/station-list",
        json={
            "curPage": 1,
            "pageSize": 10,
            "gridConnectedTime": "",
            "queryTime": get_day_start_sec(),
            "timeZone": 2,
            "sortId": "createTime",
            "sortDir": "DESC",
            "locale": "en_US",
        },
    )
    r.raise_for_status()
    obj_tree = r.json()
    if not obj_tree["success"]:
        raise FusionSolarException("Failed to retrieve station list")
    return obj_tree["data"]["list"]


def get_plant_flow(client: Any, plant_id: str) -> dict:
    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/energy-flow",
        params={"stationDn": plant_id, "_": round(time.time() * 1000)},
    )
    r.raise_for_status()
    flow_data = r.json()
    if not flow_data["success"] or "data" not in flow_data:
        raise FusionSolarException(f"Failed to retrieve plant flow for {plant_id}")
    return flow_data


def get_plant_stats(client: Any, plant_id: str, query_time: int | None = None) -> dict:
    if not query_time:
        query_time = get_day_start_sec()

    r = client._session.get(
        url=f"https://{client._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/energy-balance",
        params={
            "stationDn": plant_id,
            "timeDim": 2,
            "queryTime": query_time,
            "timeZone": 2,
            "timeZoneStr": "Europe/Vienna",
            "_": round(time.time() * 1000),
        },
    )
    r.raise_for_status()
    plant_data = r.json()
    if not plant_data["success"] or "data" not in plant_data:
        raise FusionSolarException(f"Failed to retrieve plant status for {plant_id}")
    return plant_data["data"]


def get_last_plant_data(client: Any, plant_data: dict) -> dict:
    if "xAxis" not in plant_data:
        raise FusionSolarException("Invalid plant_data object passed.")

    measurement_times = plant_data["xAxis"]
    extracted_data = {}

    for key_name, key_value in plant_data.items():
        try:
            if key_name in ("xAxis", "stationTimezone", "clientTimezone", "stationDn"):
                continue
            if isinstance(key_value, list):
                extracted_data[key_name] = get_last_value(key_value, measurement_times)
            elif key_value == "--":
                extracted_data[key_name] = None
            elif key_name.startswith("exist"):
                extracted_data[key_name] = bool(key_value)
            else:
                extracted_data[key_name] = float(key_value)
        except Exception:
            client._LOGGER.debug("Failed to parse %s = %s", key_name, key_value)
            extracted_data[key_name] = None
    return extracted_data


def get_last_value(values: list, measurement_times: list) -> dict:
    found_values = []
    for index, value in enumerate(values):
        if value != "--":
            found_values.append(
                {"time": measurement_times[index], "value": float(values[index])}
            )
    if found_values:
        return found_values[-1]
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "value": None}


def get_day_start_sec() -> int:
    start_today = time.strftime("%Y-%m-%d 00:00:00", time.gmtime())
    struct_time = time.strptime(start_today, "%Y-%m-%d %H:%M:%S")
    return round(time.mktime(struct_time) * 1000)
