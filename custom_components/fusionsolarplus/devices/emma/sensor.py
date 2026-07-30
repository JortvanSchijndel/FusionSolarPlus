from typing import Any, Dict, List

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from ...device_handler import BaseDeviceHandler
from ...api.devices.emma_api import current_peak_power_kw
from .const import EMMA_CONFIG_SIGNALS, EMMA_SIGNALS


class EMMADeviceHandler(BaseDeviceHandler):
    """Handler for EMMA devices."""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_emma_data(client):
            return await self.hass.async_add_executor_job(
                client.get_emma_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_emma_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities: List = []
        unique_ids: set[str] = set()
        device_key = list(self.device_info["identifiers"])[0][1]

        for signal in EMMA_SIGNALS:
            unique_id = f"{device_key}_{signal['id']}"
            if unique_id in unique_ids:
                continue
            entities.append(
                FusionSolarEMMASensor(
                    coordinator=coordinator,
                    signal_id=signal["id"],
                    name=signal.get("custom_name", signal["name"]),
                    unit=signal.get("unit"),
                    device_info=self.device_info,
                    device_class=signal.get("device_class"),
                    state_class=signal.get("state_class"),
                    source="realtime",
                )
            )
            unique_ids.add(unique_id)

        for signal in EMMA_CONFIG_SIGNALS:
            unique_id = f"{device_key}_{signal['id']}"
            if unique_id in unique_ids:
                continue

            if signal.get("peak_schedule"):
                entities.append(
                    FusionSolarEMMAPeakScheduleSensor(
                        coordinator=coordinator,
                        signal_id=signal["id"],
                        name=signal.get("custom_name", signal["name"]),
                        unit=signal.get("unit"),
                        device_info=self.device_info,
                        device_class=signal.get("device_class"),
                        state_class=signal.get("state_class"),
                    )
                )
            else:
                entities.append(
                    FusionSolarEMMASensor(
                        coordinator=coordinator,
                        signal_id=signal["id"],
                        name=signal.get("custom_name", signal["name"]),
                        unit=signal.get("unit"),
                        device_info=self.device_info,
                        device_class=signal.get("device_class"),
                        state_class=signal.get("state_class"),
                        source="config",
                        enum_options=signal.get("enum_options"),
                    )
                )
            unique_ids.add(unique_id)

        return entities


class FusionSolarEMMASensor(CoordinatorEntity, SensorEntity):
    """Sensor for EMMA realtime or configuration signals."""

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
        source: str = "realtime",
        enum_options: list[str] | None = None,
    ):
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._source = source
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal
        if enum_options:
            self._attr_options = list(enum_options)

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

    @property
    def native_value(self) -> Any:
        """Return normalized EMMA value from API layer."""
        data = self.coordinator.data
        if not data:
            return None
        value_map = (
            data.get("config_map", {})
            if self._source == "config"
            else data.get("value_map", {})
        )
        value = value_map.get(int(self._signal_id))
        if value is None:
            return None
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return str(value)
        return value

    @property
    def available(self) -> bool:
        """Realtime: coordinator success. Config: key present in config_map."""
        if not (self.coordinator.last_update_success and self.coordinator.data):
            return False
        if self._source != "config":
            return True
        return int(self._signal_id) in self.coordinator.data.get("config_map", {})


class FusionSolarEMMAPeakScheduleSensor(CoordinatorEntity, SensorEntity):
    """Peak shaving power limit (kW) with schedule details as attributes."""

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
    def native_value(self) -> Any:
        data = self.coordinator.data
        if not data:
            return None
        periods = data.get("peak_periods") or []
        value = current_peak_power_kw(periods)
        if value is not None:
            return value
        return data.get("config_map", {}).get(int(self._signal_id))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data or {}
        periods = data.get("peak_periods") or []
        return {
            "periods": periods,
            "period_count": len(periods),
            "config_updated_at": data.get("config_updated_at"),
        }

    @property
    def available(self) -> bool:
        if not (self.coordinator.last_update_success and self.coordinator.data):
            return False
        data = self.coordinator.data
        if data.get("peak_periods"):
            return True
        return int(self._signal_id) in data.get("config_map", {})
