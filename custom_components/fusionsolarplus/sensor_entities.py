from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import CURRENCY_MAP

from datetime import datetime, time, date
from homeassistant.util.dt import now as ha_now

import logging

_LOGGER = logging.getLogger(__name__)


class FusionSolarInverterSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Inverter devices with daily energy reset handling."""

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
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

        # Custom tracking for Daily Energy
        self._last_value = None
        self._daily_max = 0
        self._last_update_day = date.today()
        self._midnight_reset_done = False

    @property
    def native_value(self):
        """Return sensor state with corrected daily energy reset handling."""
        data = self.coordinator.data
        if not data:
            return self._last_value

        # ---- Extract value as before ----
        value = None

        # PV signals
        if self._is_pv_signal:
            pv_data = data.get("pv", {})

            if isinstance(pv_data, dict):
                signals = pv_data.get("signals", {})
                signal_data = signals.get(str(self._signal_id))
                if signal_data:
                    raw_value = signal_data.get("value")
                    value = 0 if raw_value == "-" else raw_value
                else:
                    # Handle case where pv_data exists but has no signal values
                    if not signals and pv_data.get("available_pvs"):
                        value = 0

            else:
                for item in pv_data:
                    if str(item.get("id")) == str(self._signal_id):
                        raw_value = item.get("value")
                        value = 0 if raw_value == "-" else raw_value
                        break

        # Normal inverter signals
        else:
            for group in data.get("data", []):
                for signal in group.get("signals", []):
                    if signal["id"] == self._signal_id:
                        raw_value = signal.get("value")
                        # Return "-" for enumerated sensors, 0 for numeric, "Inverter is shutdown" for status when "-"
                        if raw_value == "-":
                            if self._attr_name.lower().startswith("status"):
                                value = "Inverter is Shutdown"
                            else:
                                value = "-" if self._attr_device_class == SensorDeviceClass.ENUM else 0
                        else:
                            value = raw_value
                        break

        if value is None:
            return None

        # Handle enumerated values
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return str(value)

        # Try numeric conversion
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return self._last_value

        # ---- Handle Daily Energy special case ----
        if self._attr_name.lower().startswith("daily energy"):
            today = ha_now().date()
            now_time = ha_now().time()

            # Track the highest value seen today
            if numeric_value > self._daily_max:
                self._daily_max = numeric_value

            midnight_start = datetime.strptime("00:00:00", "%H:%M:%S").time()
            midnight_end = datetime.strptime("00:00:59", "%H:%M:%S").time()

            # Check if we are in the midnight reset window and reset only once per day
            if midnight_start <= now_time < midnight_end:
                if not self._midnight_reset_done or self._last_update_day != today:
                    self._daily_max = 0
                    self._last_value = 0.0
                    self._midnight_reset_done = True
                    self._last_update_day = today
                    return 0.0
            else:
                # Outside midnight window, reset the flag so the next midnight can reset again
                self._midnight_reset_done = False

            # Before midnight: if inverter resets early (value=0), hold last max value
            if numeric_value == 0 and not self._midnight_reset_done:
                return self._daily_max

            # Normal case, return the current numeric value
            return numeric_value

        return numeric_value

    @property
    def available(self):
        return bool(self.coordinator.last_update_success and self.coordinator.data)


class FusionSolarOptimizerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Optimizer data."""

    def __init__(
        self,
        coordinator,
        optimizer_name,
        metric_key,
        custom_name,
        unit,
        device_info,
        unique_id,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ):
        super().__init__(coordinator)
        self._attr_name = f"[{optimizer_name}] {custom_name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = unique_id
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._metric_key = metric_key
        self._optimizer_name = optimizer_name

        device_id = list(device_info["identifiers"])[0][1]
        safe_name = optimizer_name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"fsp_{device_id}_{safe_name}", hass=coordinator.hass
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = (
            self.coordinator.data.get("optimizers", []) if self.coordinator.data else []
        )
        for opt in data:
            if opt.get("optName") == self._optimizer_name:
                raw_value = opt.get(self._metric_key)
                value = 0 if raw_value == "-" else raw_value
                if value is not None and isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                return value
        return None

    @property
    def available(self):
        return self.coordinator.last_update_success


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

        ENERGY_KEYS_TO_FREEZE = {
            "monthEnergy",
            "cumulativeEnergy",
            "dailyEnergy",
            "dailySelfUseEnergy",
            "dailyUseEnergy",
            "yearEnergy",
        }

        # freeze window 23:00–02:00 for selected energy sensors
        in_freeze_window = time(23, 0) <= now < time(2, 0)
        if self._key in ENERGY_KEYS_TO_FREEZE and in_freeze_window:
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

        for group in data.get("data", []):
            if "signals" in group:
                for signal in group["signals"]:
                    if signal["id"] == self._signal_id:
                        raw_value = signal.get("value")
                        value = 0 if raw_value == "-" else raw_value

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
