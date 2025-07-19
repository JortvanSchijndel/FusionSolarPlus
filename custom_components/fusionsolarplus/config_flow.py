import logging
from functools import partial
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from custom_components.fusionsolarplus.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SUBDOMAIN,
    DOMAIN,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
)
from .api.fusion_solar_py.client import FusionSolarClient
from .api.fusion_solar_py.exceptions import AuthenticationException

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPE_PLANT = "Plant"
DEVICE_TYPE_INVERTER = "Inverter"
DEVICE_TYPE_BATTERY = "Battery"
DEVICE_TYPE_POWER_SENSOR = "Power Sensor"

DEVICE_TYPE_OPTIONS = {
    "Plant": DEVICE_TYPE_PLANT,
    "Inverter": DEVICE_TYPE_INVERTER,
    "Battery": DEVICE_TYPE_BATTERY,
    "Power Sensor": DEVICE_TYPE_POWER_SENSOR,
}


class FusionSolarPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    device_options = {}

    def __init__(self):
        self.username = None
        self.password = None
        self.subdomain = None
        self.device_type = None
        self.device_options = {}
        self.client = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input:
            self.username = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            self.subdomain = user_input[CONF_SUBDOMAIN]

            suffix = ".fusionsolar.huawei.com"

            while self.subdomain.endswith(suffix):
                self.subdomain = self.subdomain[: -len(suffix)]

            try:
                self.client = await self.hass.async_add_executor_job(
                    partial(
                        FusionSolarClient,
                        self.username,
                        self.password,
                        captcha_model_path=self.hass,  # Using modelpath to pass self.hass
                        huawei_subdomain=self.subdomain,
                    )
                )
            except AuthenticationException as auth_exc:
                _LOGGER.warning(
                    "FusionSolarPlus: Invalid authentication credentials - %s",
                    str(auth_exc),
                )
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.warning(
                    "FusionSolarPlus: Unexpected error during authentication: %s",
                    str(e),
                )
                errors["base"] = "unknown"

            if not errors:
                return await self.async_step_choose_type()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SUBDOMAIN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_choose_type(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self.device_type = DEVICE_TYPE_OPTIONS[user_input[CONF_DEVICE_TYPE]]
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="choose_type",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): vol.In(DEVICE_TYPE_OPTIONS),
                }
            ),
            errors={},
        )

    async def async_step_select_device(self, user_input=None) -> FlowResult:
        if not self.device_options:
            try:
                device_options = {}

                # Handle plants ids
                if self.device_type == DEVICE_TYPE_PLANT:
                    response = await self.hass.async_add_executor_job(
                        self.client.get_plant_ids
                    )
                    for plant_id in response:
                        device_options[f"Plant (ID: {plant_id})"] = plant_id

                # Handle inverter ids
                elif self.device_type == DEVICE_TYPE_INVERTER:
                    response = await self.hass.async_add_executor_job(
                        self.client.get_device_ids
                    )
                    for device in response:
                        if device["type"] == "Inverter":
                            device_dn = device["deviceDn"]
                            device_options[f"Inverter (ID: {device_dn})"] = device_dn

                # Handle battery ids
                elif self.device_type == DEVICE_TYPE_BATTERY:
                    plant_ids = await self.hass.async_add_executor_job(
                        self.client.get_plant_ids
                    )
                    for plant_id in plant_ids:
                        battery_ids = await self.hass.async_add_executor_job(
                            self.client.get_battery_ids, plant_id
                        )

                        for battery_id in battery_ids:
                            device_options[f"Battery (ID: {battery_id})"] = battery_id

                # Handle power sensor ids
                elif self.device_type == DEVICE_TYPE_POWER_SENSOR:
                    response = await self.hass.async_add_executor_job(
                        self.client.get_device_ids
                    )
                    for device in response:
                        if device["type"] == "Power Sensor":
                            device_dn = device["deviceDn"]
                            device_options[f"Power Sensor (ID: {device_dn})"] = (
                                device_dn
                            )

                if not device_options:
                    _LOGGER.warning(
                        "FusionSolarPlus: No matching devices found for type: %s",
                        self.device_type,
                    )
                    return self.async_abort(reason="no_devices")

                self.device_options = device_options

            except Exception as e:
                _LOGGER.warning(
                    "FusionSolarPlus: Exception while fetching device list: %s", e
                )
                return self.async_abort(reason="fetch_error")

        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME]
            device_id = self.device_options[device_name]

            return self.async_create_entry(
                title=f"{device_name}",
                data={
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.password,
                    CONF_SUBDOMAIN: self.subdomain,
                    CONF_DEVICE_TYPE: self.device_type,
                    CONF_DEVICE_ID: device_id,
                    CONF_DEVICE_NAME: device_name,
                },
            )

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_NAME): vol.In(self.device_options)}
            ),
            errors={},
        )
