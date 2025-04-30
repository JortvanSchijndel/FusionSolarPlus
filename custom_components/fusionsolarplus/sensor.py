from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN

SENSOR_KEYS = {
    "Inverter status": ("Status", None),
    "Daily energy": ("Daily Energy", "kWh"),
    "Active power": ("Active Power", "W"),
    "Internal temperature": ("Internal Temp", "°C"),
    "Cumulative energy": ("Cumulative Energy", "kWh"),
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for device_id, result in coordinator.data.items():
        if result["success"]:
            for group in result["data"]:
                for signal in group.get("signals", []):
                    if signal["name"] in SENSOR_KEYS:
                        name, unit = SENSOR_KEYS[signal["name"]]
                        entities.append(FusionSolarSensor(
                            coordinator, device_id, signal["name"], name, unit
                        ))

    async_add_entities(entities)

class FusionSolarSensor(SensorEntity):
    def __init__(self, coordinator, device_id, signal_key, name, unit):
        self._coordinator = coordinator
        self._device_id = device_id
        self._signal_key = signal_key
        self._attr_name = f"Inverter {device_id} {name}"
        self._attr_native_unit_of_measurement = unit

    @property
    def state(self):
        signal = self._get_signal()
        return signal["value"] if signal else None

    def _get_signal(self):
        result = self._coordinator.data.get(self._device_id)
        if result and result["success"]:
            for group in result["data"]:
                for signal in group.get("signals", []):
                    if signal["name"] == self._signal_key:
                        return signal
        return None

    @property
    def available(self):
        return self._get_signal() is not None
