import logging
import asyncio
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from custom_components.fusionsolarplus.const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME
)
from fusion_solar_py.client import FusionSolarClient

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPE_PLANT = 'plant'
DEVICE_TYPE_INVERTER = 'inverter'

class FusionSolarPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    device_options = {}

    def __init__(self):
        self.username = None
        self.password = None
        self.device_type = None
        self.device_options = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input:
            self.username = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            })
        )

    async def async_step_select_device(self, user_input=None) -> FlowResult:
        if not self.device_options:
            try:
                client = await self.hass.async_add_executor_job(
                    FusionSolarClient, self.username, self.password
                )

                device_options = {}

                # Fetch devices
                if self.device_type == DEVICE_TYPE_PLANT:
                    response = await self.hass.async_add_executor_job(client.get_device_ids)
                    if response:
                        for device in response:
                            if device['type'] == 'Plant':
                                device_dn = device['deviceDn']
                                device_options[f"Plant (ID: {device_dn})"] = device_dn
                    else:
                        _LOGGER.error("Failed to fetch plants")
                        return self.async_abort(reason="fetch_error")

                elif self.device_type == DEVICE_TYPE_INVERTER:
                    response = await self.hass.async_add_executor_job(client.get_device_ids)
                    if response:
                        for device in response:
                            if device['type'] == 'Inverter':
                                device_dn = device['deviceDn']
                                device_options[f"Inverter (ID: {device_dn})"] = device_dn
                    else:
                        _LOGGER.error("Failed to fetch inverters")
                        return self.async_abort(reason="fetch_error")

                else:
                    _LOGGER.error("No devices found")
                    return self.async_abort(reason="no_devices")

                self.device_options = device_options

            except Exception as e:
                _LOGGER.exception("Failed to fetch device list")
                return self.async_abort(reason="fetch_error")

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME]
            return self.async_create_entry(
                title=f"{device_name}",
                data={
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.password,
                    CONF_DEVICE_TYPE: self.device_type,
                    CONF_DEVICE_ID: self.device_options[device_name],
                    CONF_DEVICE_NAME: device_name,
                }
            )

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_NAME): vol.In(self.device_options)
            }),
            errors={}
        )
