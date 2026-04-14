"""Select platform for FusionSolar Plus."""

import logging
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices.charger.select import ChargerSelectHandler
from .devices.emma.select import EMMASelectHandler

_LOGGER = logging.getLogger(__name__)


class SelectHandlerFactory:
    """Create appropriate select handlers."""

    @staticmethod
    def create_handler(hass, entry, device_info):
        device_type = entry.data.get("device_type")
        if device_type == "Charger":
            return ChargerSelectHandler(hass, entry, device_info)
        if device_type in ("SmartAssistant", "EMMA"):
            return EMMASelectHandler(hass, entry, device_info)
        return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up select platform."""
    device_name = entry.data.get("device_name")
    device_info = hass.data[DOMAIN].get(f"{entry.entry_id}_device_info")

    if not device_info:
        _LOGGER.debug(
            "Device info not found for device %s. Skipping select setup.", device_name
        )
        return

    try:
        handler = SelectHandlerFactory.create_handler(hass, entry, device_info)

        if handler is None:
            return

        coordinator = await handler.create_coordinator()
        entities = handler.create_entities(coordinator)

        _LOGGER.info(
            "Adding %d select entities for device %s", len(entities), device_name
        )
        async_add_entities(entities)

    except Exception as e:
        _LOGGER.error("Failed to set up select entities for device %s: %s", device_name, e)
