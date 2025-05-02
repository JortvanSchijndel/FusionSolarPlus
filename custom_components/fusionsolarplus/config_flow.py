import logging
import asyncio
import subprocess
import voluptuous as vol
from functools import partial
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
from fusion_solar_py.exceptions import AuthenticationException

_LOGGER = logging.getLogger(__name__)

DEVICE_TYPE_PLANT = "Plant"
DEVICE_TYPE_INVERTER = "Inverter"

DEVICE_TYPE_OPTIONS = {
    "Plant": DEVICE_TYPE_PLANT,
    "Inverter": DEVICE_TYPE_INVERTER,
}


class FusionSolarPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    device_options = {}

    def __init__(self):
        self.username = None
        self.password = None
        self.device_type = None
        self.device_options = {}



    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        # Install requirements for captcha
        try:
            # Install first dependency (py3-onnxruntime-pyc)
            cmd1 = "apk add py3-onnxruntime-pyc"
            _LOGGER.info("Running command: %s", cmd1)
            proc1 = await asyncio.create_subprocess_shell(
                cmd1,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout1, stderr1 = await proc1.communicate()

            # Log output for the first command
            _LOGGER.debug("apk add py3-onnxruntime-pyc stdout:\n%s", stdout1.decode())
            _LOGGER.debug("apk add py3-onnxruntime-pyc stderr:\n%s", stderr1.decode())

            if proc1.returncode != 0:
                _LOGGER.error("Failed to install py3-onnxruntime-pyc. Return code: %s", proc1.returncode)
            else:
                _LOGGER.info("Successfully installed py3-onnxruntime-pyc.")

            # Install second dependency (py3-opencv)
            cmd2 = "apk add py3-opencv"
            _LOGGER.info("Running command: %s", cmd2)
            proc2 = await asyncio.create_subprocess_shell(
                cmd2,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, stderr2 = await proc2.communicate()

            # Log output for the second command
            _LOGGER.debug("apk add py3-opencv stdout:\n%s", stdout2.decode())
            _LOGGER.debug("apk add py3-opencv stderr:\n%s", stderr2.decode())

            if proc2.returncode != 0:
                _LOGGER.error("Failed to install py3-opencv. Return code: %s", proc2.returncode)
            else:
                _LOGGER.info("Successfully installed py3-opencv.")

        except Exception as e:
            _LOGGER.exception("Failed to install dependencies: %s", str(e))


        if user_input:
            self.username = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]

            try:
                await self.hass.async_add_executor_job(
                    partial(
                        FusionSolarClient, self.username, self.password, captcha_model_path="./captcha_huawei.onnx"
                    )
                )
            except AuthenticationException:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.exception("Unexpected error during authentication: %s", str(e))
                errors["base"] = "unknown"

            if not errors:
                return await self.async_step_choose_type()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_choose_type(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            self.device_type = DEVICE_TYPE_OPTIONS[user_input[CONF_DEVICE_TYPE]]
            return await self.async_step_select_device()

        return self.async_show_form(
            step_id="choose_type",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_TYPE): vol.In(DEVICE_TYPE_OPTIONS),
            }),
            errors=errors,
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
                            if device['type'] == 'Inverter':
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
                    _LOGGER.error("Unknown device type or no devices found")
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
