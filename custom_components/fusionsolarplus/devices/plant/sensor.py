from typing import Dict, Any, List

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

        exist_meter = coordinator.data.get("existMeter", False)

        for signal in PLANT_SIGNALS:
            # Skip creation entirely if this signal requires a meter and no meter exists
            if signal.get("meter_required", False) and not exist_meter:
                continue

            # Skip creation if the signal is a flow signal and the value is None
            if signal["key"].startswith("flow_") and coordinator.data.get(signal["key"]) is None:
                continue

            entities.append(
                FusionSolarPlantSensor(
                    coordinator=coordinator,
                    key=signal["key"],
                    name=signal["name"],
                    unit=signal.get("unit"),
                    device_info=self.device_info,
                    device_class=signal.get("device_class"),
                    state_class=signal.get("state_class"),
                )
            )

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
