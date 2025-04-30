import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPE_PLANT = "plant"
DEVICE_TYPE_INVERTER = "inverter"

class FusionSolarPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.username = None
        self.password = None
        self.device_type = None
        self.device_options = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.username = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            return await self.async_step_select_type()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors={}
        )

    async def async_step_select_type(self, user_input=None):
        if user_input is not None:
            self.device_type = user_input[CONF_DEVICE_TYPE]
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="select_type",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_TYPE): vol.In({
                    DEVICE_TYPE_INVERTER: "Inverter",
                    DEVICE_TYPE_PLANT: "Plant"
                })
            }),
            errors={}
        )

    async def async_step_select_device(self, user_input=None):
        if not self.device_options:
            try:
                # ============================
                # TODO: Fetch device options here
                # ============================
                # Use self.username and self.password to authenticate,
                # then fetch either:
                # - a dict of { "Display Name": "device_id" } for inverters, or
                # - a dict of { "Plant Name": "plant_id" } for plants.
                #
                # For example:
                # self.device_options = {
                #     "Inverter A (12345)": "12345",
                #     "Inverter B (67890)": "67890"
                # }
                raise NotImplementedError("Fetch device/plant options here.")
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
