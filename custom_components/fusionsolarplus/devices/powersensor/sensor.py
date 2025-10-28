from typing import Dict, Any, List, Iterator

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from .const import POWER_SENSOR_SIGNALS, EMMA_A02_SIGNALS, DTSU666_FE_SIGNALS


def iter_signals(data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """
    Iterate over signal dicts in both supported payload shapes:
    - {"data": [ { "signals": [ ... ] }, ... ], ...}
    - {"<device_id>": [ { "id": ..., "name": ..., ... }, ... ], ...}
    """
    if not data:
        return
    # Case 1: Standard Power Sensor & EMMA a02 style
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        for group in data.get("data", []):
            if (
                isinstance(group, dict)
                and "signals" in group
                and isinstance(group["signals"], list)
            ):
                for signal in group["signals"]:
                    yield signal
            elif isinstance(group, list):
                for signal in group:
                    yield signal
        return

    # Case 2: DTSU666 Style
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                for signal in value:
                    yield signal


class PowerSensorDeviceHandler(BaseDeviceHandler):
    """Handler for Power Sensor devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_power_sensor_data(client):
            return await self.hass.async_add_executor_job(
                client.get_real_time_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_power_sensor_data)

    def _detect_model_and_get_signals(self, data: Dict[str, Any]):
        """Determine which signal list to use based on available signal IDs."""
        all_signal_ids = set()

        for signal in iter_signals(data):
            sid = signal.get("id")
            if sid is not None:
                try:
                    all_signal_ids.add(int(sid))
                except (ValueError, TypeError):
                    pass

        # Detect model based on specific signal IDs
        if 230700283 in all_signal_ids:
            self.model = "Emma A02"
            return EMMA_A02_SIGNALS
        elif 10001 in all_signal_ids:
            self.model = "Standard"
            return POWER_SENSOR_SIGNALS
        elif 2101249 in all_signal_ids:
            self.model = "DTSU666-FE"
            return DTSU666_FE_SIGNALS
        else:
            self.model = "Unknown"
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
        """Return the state of the sensor for either payload shape."""
        data = self.coordinator.data
        if not data:
            return None

        for signal in iter_signals(data):
            try:
                sid = int(signal.get("id"))
            except (TypeError, ValueError):
                continue
            if sid == self._signal_id:
                # prefer "realValue" if present (some devices include both)
                raw_value = signal.get("realValue", signal.get("value"))
                # previous code treated "-" as missing
                value = 0 if raw_value == "-" else raw_value

                # if there's a unit present, try to coerce to float (numeric sensor)
                if signal.get("unit"):
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return None
                else:
                    # non-numeric / enum / status - return raw or mapped value
                    return value
        return None

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
