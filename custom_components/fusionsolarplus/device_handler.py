import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .api.fusion_solar_py.client import FusionSolarClient

_LOGGER = logging.getLogger(__name__)


class BaseDeviceHandler:
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device_info: Dict[str, Any]
    ):
        self.hass = hass
        self.entry = entry
        self.device_info = device_info
        self.device_id = entry.data.get("device_id")
        self.device_name = entry.data.get("device_name")
        self.device_type = entry.data.get("device_type")

    async def create_coordinator(self) -> DataUpdateCoordinator:
        """Create and return a data update coordinator"""
        coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=f"{self.device_name} FusionSolar Data",
            update_method=self._async_get_data,
            update_interval=timedelta(seconds=15),
        )
        await coordinator.async_config_entry_first_refresh()
        return coordinator

    async def _get_client_and_retry(self, operation_func):
        client = self.hass.data[DOMAIN][self.entry.entry_id]

        username = self.entry.options.get("username", self.entry.data["username"])
        password = self.entry.options.get("password", self.entry.data["password"])
        subdomain = self.entry.options.get(
            "subdomain", self.entry.data.get("subdomain", "uni001eu5")
        )

        async def ensure_logged_in(client_instance):
            try:
                is_active = await self.hass.async_add_executor_job(
                    client_instance.is_session_active
                )
                if not is_active:
                    await self.hass.async_add_executor_job(client_instance._login)
                    is_active = await self.hass.async_add_executor_job(
                        client_instance.is_session_active
                    )
                    if not is_active:
                        raise Exception("Login completed but session still not active")
                return True
            except Exception:
                return False

        async def create_new_client():
            new_client = await self.hass.async_add_executor_job(
                partial(
                    FusionSolarClient,
                    username,
                    password,
                    captcha_model_path=self.hass,
                    huawei_subdomain=subdomain,
                )
            )
            if await self.hass.async_add_executor_job(new_client.is_session_active):
                self.hass.data[DOMAIN][self.entry.entry_id] = new_client
                return new_client
            return None

        if not await ensure_logged_in(client):
            client = await create_new_client()

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await operation_func(client)
                if response is None:
                    raise Exception("API returned None response")
                return response
            except Exception as err:
                if attempt < max_retries:
                    recovery_success = False
                    try:
                        await self.hass.async_add_executor_job(client._login)
                        if await self.hass.async_add_executor_job(
                            client.is_session_active
                        ):
                            recovery_success = True
                    except Exception:
                        pass

                    if not recovery_success:
                        try:
                            client = await create_new_client()
                            recovery_success = True
                        except Exception:
                            pass

                    if recovery_success:
                        await asyncio.sleep(2)
                    else:
                        await asyncio.sleep(1)
                else:
                    raise Exception(
                        f"Error fetching data after {max_retries + 1} attempts: {err}"
                    )

        raise Exception("Unexpected end of retry loop")

    async def _async_get_data(self) -> Dict[str, Any]:
        """Get data from the device."""
        raise NotImplementedError()

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        """Create entities for the device."""
        raise NotImplementedError()
