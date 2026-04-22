from typing import Dict, Any, List

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from .const import POWER_SENSOR_SIGNALS, EMMA_A02_SIGNALS, DTSU666_FE_SIGNALS


class PowerSensorDeviceHandler(BaseDeviceHandler):
    """Handler for Power Sensor devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_power_sensor_data(client):
            return await self.hass.async_add_executor_job(
                client.get_powersensor_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_power_sensor_data)

    def _detect_model_and_get_signals(self, data: Dict[str, Any]):
        """Determine which signal set to use from precomputed API model."""
        model = data.get("model", "Unknown")
        if model == "Emma A02":
            return EMMA_A02_SIGNALS
        if model == "DTSU666-FE":
            return DTSU666_FE_SIGNALS
        return POWER_SENSOR_SIGNALS

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Auto-detect which signals to use based on which model
        signals = self._detect_model_and_get_signals(coordinator.data or {})

        for signal in signals:
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


class FusionSolarPowerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Power Sensor"""

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
        self._signal_id = int(signal_id)
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
        """Return normalized value from API layer."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("value_map", {}).get(self._signal_id)

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
