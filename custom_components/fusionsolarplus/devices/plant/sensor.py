from typing import Dict, Any, List
from datetime import datetime, time

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from .const import PLANT_SIGNALS
from ...const import CURRENCY_MAP


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


class FusionSolarPlantSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Plant devices."""

    def __init__(
        self,
        coordinator,
        key,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
    ):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._base_unit = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{key}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

        # cache for freeze logic
        self._last_valid_value = None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._key == "dailyIncome":
            data = self.coordinator.data
            if data:
                currency_num = data.get("currency")
                if currency_num:
                    return CURRENCY_MAP.get(currency_num, str(currency_num))
        return self._base_unit

    @property
    def native_value(self):
        """Return the state of the sensor with freeze logic between 23:00–02:00."""
        now = datetime.now().time()

        # Define freeze window
        freeze_start = time(22, 0)
        freeze_end = time(3, 0)

        energy_keys_to_freeze = {
            "monthEnergy",
            "cumulativeEnergy",
            "dailyEnergy",
            "dailySelfUseEnergy",
            "dailyUseEnergy",
            "yearEnergy",
        }

        if self._key in energy_keys_to_freeze:
            if freeze_start <= now or now <= freeze_end:
                return self._last_valid_value

        # otherwise use live data
        data = self.coordinator.data
        if not data:
            return self._last_valid_value

        raw_value = data.get(self._key)
        if raw_value is None or raw_value == "-":
            return self._last_valid_value

        try:
            value = float(raw_value) if self.native_unit_of_measurement else raw_value
        except (TypeError, ValueError):
            return self._last_valid_value

        # cache valid values for later freeze
        self._last_valid_value = value
        return value

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
