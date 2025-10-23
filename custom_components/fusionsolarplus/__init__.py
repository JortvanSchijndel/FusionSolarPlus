from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .api.fusion_solar_py.client import FusionSolarClient
from functools import partial

DOMAIN = "fusionsolarplus"


async def async_setup_entry(hass, entry):
    entry.async_on_unload(entry.add_update_listener(update_listener))

    username = entry.options.get("username", entry.data["username"])
    password = entry.options.get("password", entry.data["password"])
    subdomain = entry.options.get("subdomain", entry.data.get("subdomain", "uni001eu5"))
    installer = entry.options.get("installer", entry.data.get("installer"))
    print(installer)

    client = await hass.async_add_executor_job(
        partial(
            FusionSolarClient,
            username,
            password,
            captcha_model_path=hass,
            huawei_subdomain=subdomain,
        )
    )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Store client integration data
    hass.data[DOMAIN][entry.entry_id] = client

    # Register device
    device_registry = async_get_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(entry.data["device_id"]))},
        manufacturer="FusionSolar",
        name=entry.data["device_name"],
        model=entry.data["device_type"],
    )

    # Forward entry so sensors can be created
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    # Remove stored client and data
    hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
