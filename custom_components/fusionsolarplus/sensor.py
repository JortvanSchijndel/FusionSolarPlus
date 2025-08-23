import asyncio
import re
import logging
from datetime import timedelta
from functools import partial
from typing import List, Dict, Any, Set

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INVERTER_SIGNALS,
    PLANT_SIGNALS,
    CHARGING_PILE_SIGNALS,
    CHARGER_DEVICE_SIGNALS,
    BATTERY_STATUS_SIGNALS,
    POWER_SENSOR_SIGNALS,
    PV_SIGNALS,
    MODULE_SIGNAL_MAP,
    OPTIMIZER_METRICS,
)
from .sensor_entities import (
    FusionSolarInverterSensor,
    FusionSolarPlantSensor,
    FusionSolarBatterySensor,
    FusionSolarBatteryModuleSensor,
    FusionSolarPowerSensor,
    FusionSolarOptimizerSensor,
    FusionSolarChargerSensor,
)
from .api.fusion_solar_py.client import FusionSolarClient

_LOGGER = logging.getLogger(__name__)


pv_inputs = {
    "pv1": {"voltage": "11001", "current": "11002"},
    "pv2": {"voltage": "11004", "current": "11005"},
    "pv3": {"voltage": "11007", "current": "11008"},
    "pv4": {"voltage": "11010", "current": "11011"},
}


class BaseDeviceHandler:
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device_info: Dict[str, Any]
    ):
        self.hass = hass
        self.entry = entry
        self.device_info = device_info
        self.device_id = entry.data.get("device_id")
        self.device_name = entry.data.get("device_name")
        self.device_type = entry.data.get("device_type")

    async def create_coordinator(self) -> DataUpdateCoordinator:
        """Create and return a data update coordinator"""
        coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=f"{self.device_name} FusionSolar Data",
            update_method=self._async_get_data,
            update_interval=timedelta(seconds=15),
        )
        await coordinator.async_config_entry_first_refresh()
        return coordinator

    async def _get_client_and_retry(self, operation_func):
        """Common client management and retry logic"""
        client = self.hass.data[DOMAIN][self.entry.entry_id]
        username = self.entry.data["username"]
        password = self.entry.data["password"]
        subdomain = self.entry.data.get("subdomain", "uni001eu5")

        async def ensure_logged_in(client_instance):
            try:
                is_active = await self.hass.async_add_executor_job(
                    client_instance.is_session_active
                )
                if not is_active:
                    await self.hass.async_add_executor_job(client_instance._login)
                    is_active = await self.hass.async_add_executor_job(
                        client_instance.is_session_active
                    )
                    if not is_active:
                        raise Exception("Login completed but session still not active")
                return True
            except Exception:
                return False

        async def create_new_client():
            new_client = await self.hass.async_add_executor_job(
                partial(
                    FusionSolarClient,
                    username,
                    password,
                    captcha_model_path=self.hass,
                    huawei_subdomain=subdomain,
                )
            )
            if await self.hass.async_add_executor_job(new_client.is_session_active):
                self.hass.data[DOMAIN][self.entry.entry_id] = new_client
                return new_client
            return None

        if not await ensure_logged_in(client):
            client = await create_new_client()

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await operation_func(client)
                if response is None:
                    raise Exception("API returned None response")
                return response
            except Exception as err:
                if attempt < max_retries:
                    recovery_success = False
                    try:
                        await self.hass.async_add_executor_job(client._login)
                        if await self.hass.async_add_executor_job(
                            client.is_session_active
                        ):
                            recovery_success = True
                    except Exception:
                        pass

                    if not recovery_success:
                        try:
                            client = await create_new_client()
                            recovery_success = True
                        except Exception:
                            pass

                    if recovery_success:
                        await asyncio.sleep(2)
                    else:
                        await asyncio.sleep(1)
                else:
                    raise Exception(
                        f"Error fetching data after {max_retries + 1} attempts: {err}"
                    )

        raise Exception("Unexpected end of retry loop")


class InverterDeviceHandler(BaseDeviceHandler):
    """Handler for Inverter devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_inverter_data(client):
            # Get real-time data
            response = await self.hass.async_add_executor_job(
                client.get_real_time_data, self.device_id
            )

            # Get optimizer stats
            optimizer_stats = await self.hass.async_add_executor_job(
                client.get_optimizer_stats, self.device_id
            )
            response["optimizers"] = optimizer_stats

            # Get PV info
            pv_stats = await self.hass.async_add_executor_job(
                client.get_pv_info, self.device_id
            )

            response["pv"] = pv_stats

            return response

        return await self._get_client_and_retry(fetch_inverter_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Create normal inverter entities
        for signal in INVERTER_SIGNALS:
            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['id']}"
            if unique_id not in unique_ids:
                entity = FusionSolarInverterSensor(
                    coordinator,
                    signal["id"],
                    signal.get("custom_name", signal["name"]),
                    signal.get("unit", None),
                    self.device_info,
                    signal.get("device_class"),
                    signal.get("state_class"),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

        self._create_pv_entities(coordinator, entities, unique_ids)

        self._create_optimizer_entities(coordinator, entities, unique_ids)

        return entities

    def _create_pv_entities(
        self, coordinator: DataUpdateCoordinator, entities: List, unique_ids: Set[str]
    ):
        if not coordinator.data:
            return

        pv_data = coordinator.data.get("pv", {})

        signals = pv_data.get("signals", {})
        pv_lookup = {
            signal_id: signal_data.get("value")
            for signal_id, signal_data in signals.items()
        }
        available_pvs = {pv.lower() for pv in pv_data.get("available_pvs", [])}

        signals_to_input = {
            "PV1": ("11001", "11002", "11003"),
            "PV2": ("11004", "11005", "11006"),
            "PV3": ("11007", "11008", "11009"),
            "PV4": ("11010", "11011", "11012"),
            "PV5": ("11013", "11014", "11015"),
            "PV6": ("11016", "11017", "11018"),
            "PV7": ("11019", "11020", "11021"),
            "PV8": ("11022", "11023", "11024"),
            "PV9": ("11025", "11026", "11027"),
            "PV10": ("11028", "11029", "11030"),
            "PV11": ("11031", "11032", "11033"),
            "PV12": ("11034", "11035", "11036"),
            "PV13": ("11037", "11038", "11039"),
            "PV14": ("11040", "11041", "11042"),
            "PV15": ("11043", "11044", "11045"),
            "PV16": ("11046", "11047", "11048"),
            "PV17": ("11049", "11050", "11051"),
            "PV18": ("11052", "11053", "11054"),
            "PV19": ("11055", "11056", "11057"),
            "PV20": ("11058", "11059", "11060"),
        }

        for pv_name in available_pvs:
            pv_key = pv_name.upper()

            signal_ids = signals_to_input.get(pv_key)
            if not signal_ids:
                continue

            for sig_id in signal_ids:
                pv_signal = next(
                    (ps for ps in PV_SIGNALS if str(ps["id"]) == sig_id), None
                )
                if not pv_signal:
                    continue

                if sig_id not in pv_lookup or pv_lookup[sig_id] is None:
                    continue

                unique_id = f"{list(self.device_info['identifiers'])[0][1]}_pv_{sig_id}"
                if unique_id in unique_ids:
                    continue

                entity = FusionSolarInverterSensor(
                    coordinator,
                    int(sig_id),
                    pv_signal["custom_name"],
                    pv_signal["unit"],
                    self.device_info,
                    pv_signal.get("device_class"),
                    pv_signal.get("state_class"),
                    is_pv_signal=True,
                )
                entities.append(entity)
                unique_ids.add(unique_id)

    def _create_optimizer_entities(
        self, coordinator: DataUpdateCoordinator, entities: List, unique_ids: Set[str]
    ):
        """Create optimizer entities"""
        if not coordinator.data:
            return

        optimizers = coordinator.data.get("optimizers", [])
        for optimizer in optimizers:
            optimizer_name = optimizer.get("optName", "Optimizer")
            for metric in OPTIMIZER_METRICS:
                metric_key = metric["name"]
                value = optimizer.get(metric_key)
                if value is not None:
                    unique_id = f"{self.device_id}_{optimizer_name}_{metric_key}"
                    if unique_id not in unique_ids:
                        entity = FusionSolarOptimizerSensor(
                            coordinator,
                            optimizer_name,
                            metric["name"],
                            metric.get("custom_name", metric["name"]),
                            metric.get("unit"),
                            self.device_info,
                            unique_id,
                            device_class=metric.get("device_class"),
                            state_class=metric.get("state_class"),
                            entity_category=EntityCategory.DIAGNOSTIC,
                        )
                        entities.append(entity)
                        unique_ids.add(unique_id)


class ChargerDeviceHandler(BaseDeviceHandler):
    """Handler for Charger devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_charger_data(client):
            return await self.hass.async_add_executor_job(
                client.get_charger_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_charger_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        if not coordinator.data:
            return entities

        for signal_type_id, signals_data in coordinator.data.items():
            if not isinstance(signals_data, list):
                continue

            signal_list = self._get_signal_list_for_type(signals_data)

            if not signal_list:
                continue

            for signal_config in signal_list:
                matching_signal = next(
                    (s for s in signals_data if s.get("id") == signal_config["id"]),
                    None,
                )

                if matching_signal:
                    unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal_config['id']}"
                    if unique_id not in unique_ids:
                        entity = FusionSolarChargerSensor(
                            coordinator,
                            signal_config["id"],
                            signal_config.get("custom_name", signal_config["name"]),
                            signal_config.get("unit", None),
                            self.device_info,
                            signal_config.get("device_class"),
                            signal_config.get("state_class"),
                            signal_type_id,
                        )
                        entities.append(entity)
                        unique_ids.add(unique_id)

        return entities

    def _get_signal_list_for_type(self, signals_data):
        """Determine which signal list to use based on the signals present in the data"""
        if not signals_data:
            return None

        present_ids = {signal.get("id") for signal in signals_data if signal.get("id")}

        charging_pile_ids = {
            10001,
            10002,
            10003,
            10004,
        }
        if charging_pile_ids.intersection(present_ids):
            if any(
                signal.get("name") == "Charging Connector No."
                for signal in signals_data
            ):
                return CHARGING_PILE_SIGNALS

        charger_device_ids = {
            10001,
            10002,
            455770003,
        }
        if charger_device_ids.intersection(present_ids):
            if any(signal.get("name") == "Software Version" for signal in signals_data):
                return CHARGER_DEVICE_SIGNALS

        return None


class PlantDeviceHandler(BaseDeviceHandler):
    """Handler for Plant devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_plant_data(client):
            return await self.hass.async_add_executor_job(
                client.get_current_plant_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_plant_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Check if meter exists
        exist_meter = (
            coordinator.data.get("existMeter", True) if coordinator.data else True
        )

        # Filter plant signals based on meter
        plant_signals_filtered = [
            signal
            for signal in PLANT_SIGNALS
            if exist_meter
            or signal["key"] not in ["dailySelfUseEnergy", "dailyUseEnergy"]
        ]

        for signal in plant_signals_filtered:
            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['key']}"
            if unique_id not in unique_ids:
                entity = FusionSolarPlantSensor(
                    coordinator,
                    signal["key"],
                    signal.get("custom_name", signal["name"]),
                    signal.get("unit", None),
                    self.device_info,
                    signal.get("device_class"),
                    signal.get("state_class"),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

        return entities


class BatteryDeviceHandler(BaseDeviceHandler):
    """Handler for Battery devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_battery_data(client):
            # Get battery data
            response = await self.hass.async_add_executor_job(
                client.get_battery_status, self.device_id
            )

            # Get module data
            module_data = {}
            for module_id in ["1", "2", "3", "4"]:
                stats = await self.hass.async_add_executor_job(
                    client.get_battery_module_stats, self.device_id, module_id
                )
                if stats:
                    module_data[module_id] = stats

            return {"battery": response, "modules": module_data}

        return await self._get_client_and_retry(fetch_battery_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Create battery entities
        for signal in BATTERY_STATUS_SIGNALS:
            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['id']}"
            if unique_id not in unique_ids:
                entity = FusionSolarBatterySensor(
                    coordinator,
                    signal["id"],
                    signal.get("custom_name", signal["name"]),
                    signal.get("unit", None),
                    self.device_info,
                    signal.get("device_class"),
                    signal.get("state_class"),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

        self._create_battery_module_entities(coordinator, entities, unique_ids)

        return entities

    def _create_battery_module_entities(
        self, coordinator: DataUpdateCoordinator, entities: List, unique_ids: Set[str]
    ):
        """Create battery module entities"""
        if not coordinator.data:
            return

        modules_data = coordinator.data.get("modules", {})
        for module_id, module_signals in MODULE_SIGNAL_MAP.items():
            module_signals_data = modules_data.get(module_id)
            if not module_signals_data:
                continue

            # Find valid battery packs
            valid_packs = set()
            for signal in module_signals_data:
                name = signal.get("name", "")
                match = re.search(r"\[Battery pack (\d+)\] SN", name, re.IGNORECASE)
                if match and signal.get("realValue"):
                    valid_packs.add(match.group(1))

            # Create entities for valid packs
            for signal in module_signals:
                name = signal.get("name", "")
                pack_match = re.search(r"Battery pack (\d+)", name, re.IGNORECASE)
                if pack_match:
                    pack_no = pack_match.group(1)
                    if pack_no not in valid_packs:
                        continue

                unique_id = f"{list(self.device_info['identifiers'])[0][1]}_module{module_id}_{signal['id']}"
                if unique_id not in unique_ids:
                    entity = FusionSolarBatteryModuleSensor(
                        coordinator,
                        signal["id"],
                        signal.get("custom_name", signal["name"]),
                        signal.get("unit", None),
                        self.device_info,
                        module_id,
                        signal.get("device_class"),
                        signal.get("state_class"),
                    )
                    entities.append(entity)
                    unique_ids.add(unique_id)


class PowerSensorDeviceHandler(BaseDeviceHandler):
    """Handler for Power Sensor devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_power_sensor_data(client):
            return await self.hass.async_add_executor_job(
                client.get_real_time_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_power_sensor_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        for signal in POWER_SENSOR_SIGNALS:
            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['id']}"
            if unique_id not in unique_ids:
                entity = FusionSolarPowerSensor(
                    coordinator,
                    signal["id"],
                    signal.get("custom_name", signal["name"]),
                    signal.get("unit", None),
                    self.device_info,
                    signal.get("device_class"),
                    signal.get("state_class"),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

        return entities


class DeviceHandlerFactory:
    """Create appropriate device handlers"""

    @staticmethod
    def create_handler(
        hass: HomeAssistant, entry: ConfigEntry, device_info: Dict[str, Any]
    ) -> BaseDeviceHandler:
        device_type = entry.data.get("device_type")

        if device_type == "Inverter":
            return InverterDeviceHandler(hass, entry, device_info)
        elif device_type == "Plant":
            return PlantDeviceHandler(hass, entry, device_info)
        elif device_type == "Battery":
            return BatteryDeviceHandler(hass, entry, device_info)
        elif device_type == "Power Sensor":
            return PowerSensorDeviceHandler(hass, entry, device_info)
        elif device_type == "Charger":
            return ChargerDeviceHandler(hass, entry, device_info)
        else:
            raise ValueError(f"Unsupported device type: {device_type}")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up sensor platform."""
    device_id = entry.data.get("device_id")
    device_name = entry.data.get("device_name")
    device_type = entry.data.get("device_type")

    device_info = {
        "identifiers": {(DOMAIN, str(device_id))},
        "name": device_name,
        "manufacturer": "FusionSolar",
        "model": device_type or "Unknown",
        "via_device": None,
    }

    try:
        # Create device handler
        handler = DeviceHandlerFactory.create_handler(hass, entry, device_info)

        # Create coordinator
        coordinator = await handler.create_coordinator()

        # Create entities
        entities = handler.create_entities(coordinator)

        _LOGGER.info("Adding %d entities for device %s", len(entities), device_name)
        async_add_entities(entities)

    except Exception as e:
        _LOGGER.error("Failed to set up device %s: %s", device_name, e)
        raise
