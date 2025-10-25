from typing import Dict, Any, List

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from .const import (
    CHARGING_PILE_SIGNALS,
    CHARGER_DEVICE_SIGNALS,
)


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


class FusionSolarChargerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Charger devices."""

    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
        signal_type_id=None,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._signal_type_id = signal_type_id
        self._attr_name = name
        self._base_unit = unit
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
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._base_unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        # Find the signal data for this sensor
        signal_data = None
        for signal_type_id, signals_list in data.items():
            if isinstance(signals_list, list):
                signal_data = next(
                    (s for s in signals_list if s.get("id") == self._signal_id), None
                )
                if signal_data:
                    break

        if not signal_data:
            return None

        # Get the real value from the signal data
        raw_value = signal_data.get("realValue")
        if raw_value is None:
            return None

        # Handle special cases
        value = 0 if raw_value == "-" else raw_value

        # Handle enum values - return the real value (text) for enum types
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return value

        # For numeric values, try to convert to float if unit is present
        if self.native_unit_of_measurement:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        else:
            return value

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
