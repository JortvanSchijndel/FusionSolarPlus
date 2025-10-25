import logging
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
)

from .devices.inverter.sensor import InverterDeviceHandler
from .devices.plant.sensor import PlantDeviceHandler
from .devices.charger.sensor import ChargerDeviceHandler
from .devices.battery.sensor import BatteryDeviceHandler
from .devices.powersensor.sensor import PowerSensorDeviceHandler

from .device_handler import BaseDeviceHandler

_LOGGER = logging.getLogger(__name__)


class DeviceHandlerFactory:
    """Create appropriate device handlers"""

    @staticmethod
    def create_handler(
        hass: HomeAssistant, entry: ConfigEntry, device_info: Dict[str, Any]
    ) -> BaseDeviceHandler:
        device_type = entry.data.get("device_type")

        if device_type == "Inverter":
            return InverterDeviceHandler(hass, entry, device_info)
        elif device_type == "Plant":
            return PlantDeviceHandler(hass, entry, device_info)
        elif device_type == "Battery":
            return BatteryDeviceHandler(hass, entry, device_info)
        elif device_type == "Power Sensor":
            return PowerSensorDeviceHandler(hass, entry, device_info)
        elif device_type == "Charger":
            return ChargerDeviceHandler(hass, entry, device_info)
        else:
            raise ValueError(f"Unsupported device type: {device_type}")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up sensor platform."""
    device_id = entry.data.get("device_id")
    device_name = entry.data.get("device_name")
    device_type = entry.data.get("device_type")

    device_info = {
        "identifiers": {(DOMAIN, str(device_id))},
        "name": device_name,
        "manufacturer": "FusionSolar",
        "model": device_type or "Unknown",
        "via_device": None,
    }

    try:
        # Create device handler
        handler = DeviceHandlerFactory.create_handler(hass, entry, device_info)

        # Create coordinator
        coordinator = await handler.create_coordinator()

        # Create entities
        entities = handler.create_entities(coordinator)

        _LOGGER.info("Adding %d entities for device %s", len(entities), device_name)
        async_add_entities(entities)

    except Exception as e:
        _LOGGER.error("Failed to set up device %s: %s", device_name, e)
        raise
