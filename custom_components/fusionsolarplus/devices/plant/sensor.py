from typing import Dict, Any, List
from datetime import datetime, timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
            if (
                signal["key"].startswith("flow_")
                and coordinator.data.get(signal["key"]) is None
            ):
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

        self._SIGNIFICANT_DROP_FRACTION = 0.25
        self._RESET_NEAR_ZERO_THRESHOLD = 1
        self._SPIKE_THRESHOLD_FRACTION = 0.25
        self._SPIKE_MIN_ABSOLUTE = 5.0  # Never flag a spike smaller than this
        self._last_valid_value = None
        self._last_reset_time = None
        self.RESET_COOLDOWN = timedelta(hours=6)

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

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
        data = self.coordinator.data
        if not data:
            return None
        value = data.get(self._key)
        if value is None:
            return None

        # The scraped portal can still yield non-numeric values.
        # Coerce here so a stray string can never reach the numeric
        # comparisons below nor be stored in _last_valid_value.
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        # --- Spike suppression ---
        if self._last_valid_value is not None and self._last_valid_value > 0:
            absolute_jump = value - self._last_valid_value
            relative_jump = absolute_jump / self._last_valid_value
            if (
                relative_jump > self._SPIKE_THRESHOLD_FRACTION
                and absolute_jump > self._SPIKE_MIN_ABSOLUTE
            ):
                return None

        # --- TOTAL_INCREASING drop / reset handling ---
        if (
            self._attr_state_class == SensorStateClass.TOTAL_INCREASING
            and self._last_valid_value is not None
            and self._last_valid_value > 0
            and value < self._last_valid_value
        ):
            drop_fraction = (self._last_valid_value - value) / self._last_valid_value

            is_near_zero = value <= self._RESET_NEAR_ZERO_THRESHOLD

            # Check cooldown
            in_cooldown = (
                self._last_reset_time is not None
                and datetime.utcnow() - self._last_reset_time < self.RESET_COOLDOWN
            )

            if drop_fraction > self._SIGNIFICANT_DROP_FRACTION:
                if is_near_zero:
                    if not in_cooldown:
                        self._last_reset_time = datetime.utcnow()
                    else:
                        return None
                else:
                    return None

        self._last_valid_value = value
        return value

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
