from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .coordinator import FusionSolarCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = FusionSolarCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
