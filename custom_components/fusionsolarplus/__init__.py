from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .api.fusion_solar_py.client import FusionSolarClient
from functools import partial
import os

DOMAIN = "fusionsolarplus"


async def async_setup_entry(hass, entry):
    username = entry.data["username"]
    password = entry.data["password"]
    subdomain = entry.data.get("subdomain", "uni001eu5")

    model_path = os.path.join(os.path.dirname(__file__), "captcha_huawei.onnx")

    client = await hass.async_add_executor_job(
        partial(
            FusionSolarClient,
            username,
            password,
            captcha_model_path=model_path,
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
