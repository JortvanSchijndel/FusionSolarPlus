from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import CURRENCY_MAP


class FusionSolarInverterSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Inverter devices."""

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

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None

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
                        value = 0 if raw_value == "-" else raw_value
                        break

        if value is None:
            return None

        # Handle enumerated values
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return str(value)

        # Handle numeric values
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)

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

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        # Set currency unit dynamically from API
        if self._key == "dailyIncome":
            data = self.coordinator.data
            if data:
                currency_num = data.get("currency")
                if currency_num:
                    return CURRENCY_MAP.get(currency_num, str(currency_num))
        return self._base_unit

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if not data:
            return None

        raw_value = data.get(self._key)
        if raw_value is None:
            return None

        value = 0 if raw_value == "-" else raw_value

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
