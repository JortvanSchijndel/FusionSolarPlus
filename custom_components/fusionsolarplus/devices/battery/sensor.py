from typing import Dict, Any, List, Set
import re

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import generate_entity_id, EntityCategory
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from .const import (
    BATTERY_STATUS_SIGNALS,
    MODULE_SIGNAL_MAP,
)


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


class FusionSolarBatterySensor(CoordinatorEntity, SensorEntity):
    """Sensor for Battery devices."""

    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        signals = data.get("battery", [])
        if not signals:
            return None

        for signal in signals:
            value = 0 if signal.get("value") == "-" else signal.get("value")

            if signal["id"] == self._signal_id:
                if signal.get("unit"):
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return None
                else:
                    return value
        return None

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


class FusionSolarBatteryModuleSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Battery Module data."""

    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        module_id,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{list(device_info['identifiers'])[0][1]}_module{module_id}_{signal_id}"
        )
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._module_id = module_id

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data or "modules" not in data:
            return None

        module_signals = data["modules"].get(self._module_id, [])
        for signal in module_signals:
            if signal["id"] == self._signal_id:
                raw_value = signal.get("realValue")
                value = 0 if raw_value == "-" else raw_value
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return value
        return None

    @property
    def available(self):
        data = self.coordinator.data
        return (
            self.coordinator.last_update_success
            and data is not None
            and "modules" in data
            and self._module_id in data["modules"]
            and bool(data["modules"][self._module_id])
        )
