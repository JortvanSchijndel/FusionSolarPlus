"""custom_components/fusionsolarplus/number.py"""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    device_type = entry.data.get("device_type")
    if device_type == "Charger":
        from .devices.charger.number import async_setup_entry as setup
        await setup(hass, entry, async_add_entities)
    else:
        _LOGGER.debug("No number entities for device type '%s'", device_type)
