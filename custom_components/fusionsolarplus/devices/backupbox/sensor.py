from typing import Dict, Any, List

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from ...entity_naming import (
    configure_sensor_names,
    entity_id_slug,
    signal_entity_id_name,
)
from .const import BACKUPBOX_SIGNALS


class BackupBoxDeviceHandler(BaseDeviceHandler):
    """Handler for BackupBox devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_backupbox_data(client):
            # Get real-time data
            return await self.hass.async_add_executor_job(
                client.get_backupbox_data, self.device_id
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

            api_name = (
                (coordinator.data or {}).get("signal_names", {}).get(int(signal["id"]))
            )
            entity = FusionSolarBackupBoxSensor(
                coordinator=coordinator,
                signal_id=signal["id"],
                translation_key=signal["translation_key"],
                unit=signal.get("unit"),
                device_info=self.device_info,
                device_class=signal.get("device_class"),
                state_class=signal.get("state_class"),
                api_name=api_name,
                entity_id_name=signal_entity_id_name(signal),
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
        translation_key,
        unit,
        device_info,
        device_class=None,
        state_class=None,
        is_pv_signal=False,
        api_name=None,
        entity_id_name=None,
    ):
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._signal_id = signal_id
        configure_sensor_names(self, translation_key=translation_key, api_name=api_name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal

        device_id = list(device_info["identifiers"])[0][1]
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_{entity_id_slug(entity_id_name)}",
            hass=coordinator.hass,
        )

    @property
    def native_value(self) -> Any:
        """Return normalized BackupBox value from API layer."""
        data = self.coordinator.data
        if not data:
            return None
        value = data.get("value_map", {}).get(int(self._signal_id))
        if value is None:
            return None
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return str(value)
        return value

    @property
    def available(self) -> bool:
        """Return True if data is successfully retrieved."""
        return bool(self.coordinator.last_update_success and self.coordinator.data)
