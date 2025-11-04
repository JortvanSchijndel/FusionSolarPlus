from typing import Dict, Any, List, Set
from datetime import date, datetime

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import generate_entity_id, EntityCategory
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.util.dt import now as ha_now

from ...device_handler import BaseDeviceHandler
from .const import (
    BACKUPBOX_SIGNALS
)


class BackupBoxDeviceHandler(BaseDeviceHandler):
    """Handler for BackupBox devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_backupbox_data(client):
            # Get real-time data
            return await self.hass.async_add_executor_job(
                client.get_real_time_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_backupbox_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Create normal BackupBox entities
        for signal in BACKUPBOX_SIGNALS:
            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['id']}"
            if unique_id in unique_ids:
                continue

            entity = FusionSolarBackupBoxSensor(
                coordinator=coordinator,
                signal_id=signal["id"],
                name=signal.get("custom_name", signal["name"]),
                unit=signal.get("unit"),
                device_info=self.device_info,
                device_class=signal.get("device_class"),
                state_class=signal.get("state_class"),
            )
            entities.append(entity)
            unique_ids.add(unique_id)

        return entities


class FusionSolarBackupBoxSensor(CoordinatorEntity, SensorEntity):
    """Sensor for BackupBox devices with support for enumerated and numeric signals."""

    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
        is_pv_signal=False,
    ):
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal
        self._last_value: Any = None

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        data = self.coordinator.data
        if not data:
            return self._last_value

        # Extract signal data from response
        try:
            signals = []
            for item in data.get("data", []):
                if isinstance(item, dict) and "signals" in item:
                    signals.extend(item["signals"])

            signal_data = next(
                (s for s in signals if s.get("id") == self._signal_id), None
            )
            if not signal_data:
                return self._last_value

            value = signal_data.get("value")
            if value is None:
                return None

            # Try converting numeric values to float
            try:
                numeric_value = float(value)
                self._last_value = numeric_value
                return numeric_value
            except (ValueError, TypeError):
                pass

            # Handle enumerated values (status, etc.)
            if self._attr_device_class == SensorDeviceClass.ENUM:
                self._last_value = str(value)
                return str(value)

            self._last_value = value
            return value

        except Exception as err:
            # Safe fallback on any parsing error
            return self._last_value

    @property
    def available(self) -> bool:
        """Return True if data is successfully retrieved."""
        return bool(self.coordinator.last_update_success and self.coordinator.data)