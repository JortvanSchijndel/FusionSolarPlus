from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .api.fusion_solar_py.client import FusionSolarClient
from functools import partial


DOMAIN = "fusionsolarplus"

async def async_setup_entry(hass, entry):
    username = entry.data["username"]
    password = entry.data["password"]

    client = await hass.async_add_executor_job(
        partial(FusionSolarClient, username, password, captcha_model_path=hass)
    )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = client


    device_registry = async_get_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data["device_name"])},
        manufacturer="FusionSolar",
        name=entry.data["device_name"],
        model=entry.data["device_type"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
