"""Switch platform for Inverter devices."""
import asyncio
import logging
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from ...device_handler import BaseDeviceHandler
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class InverterSwitchHandler(BaseDeviceHandler):
    """Handler for inverter switches."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_info: Dict[str, Any],
    ):
        super().__init__(hass, entry, device_info)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        """Create switch entities for the inverter."""
        client = self.hass.data[DOMAIN][self.entry.entry_id]
        password = self.entry.options.get("password", self.entry.data.get("password"))

        return [
            InverterPowerSwitch(
                coordinator,
                self.hass,
                self.device_info,
                self.device_id,
                self.device_name,
                client,
                password,
            )
        ]


class InverterPowerSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an Inverter Power Switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        hass: HomeAssistant,
        device_info: Dict[str, Any],
        device_id: str,
        device_name: str,
        client,
        password: str,
    ):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.hass = hass
        self._device_info = device_info
        self._device_id = device_id
        self._device_name = device_name
        self._client = client
        self._password = password
        self._is_on = True  # Default to on, will be updated by is_on property
        self._is_toggling = False
        self._attr_unique_id = f"{device_id}_power_switch"
        self._attr_name = f"{device_name} Power"

    @property
    def device_info(self):
        """Return device information."""
        return self._device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._is_toggling and self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return true if the inverter is on based on coordinator data."""
        if self.coordinator.data and self.coordinator.data.get("data"):
            for group in self.coordinator.data["data"]:
                if "signals" in group:
                    for signal in group["signals"]:
                        if signal.get("id") == 10025:  # Inverter status signal
                            inverter_status_value = signal.get("value")
                            # The inverter is off if the status is "-" or "OFF: instructed shutdown"
                            off_states = ["-", "OFF : instructed shutdown"]
                            current_state = inverter_status_value not in off_states
                            self._is_on = current_state  # Cache the latest state
                            return current_state

        # Fallback to the last known/optimistic state if data is unavailable
        return self._is_on

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:power" if self.is_on else "mdi:power-off"

    async def _toggle_device(self, signal: str, new_state: bool):
        """Send a toggle command to the device and handle cooldown."""
        if self._is_toggling:
            _LOGGER.warning("Inverter is already changing state. Please wait.")
            return

        self._is_toggling = True
        self._is_on = new_state  # Optimistically update the state
        self.async_write_ha_state()

        try:
            success = await self.hass.async_add_executor_job(
                self._client.toggle_device,
                self._device_id,
                signal,
                self._password,
                "0",
            )
            if success:
                _LOGGER.info(
                    "Successfully sent turn %s command to inverter.",
                    "on" if new_state else "off",
                )
            else:
                _LOGGER.error(
                    "Failed to send turn %s command to inverter.",
                    "on" if new_state else "off",
                )
                self._is_on = not new_state

        except Exception as e:
            _LOGGER.error("An error occurred while toggling inverter: %s", e)
            self._is_on = not new_state
        finally:
            # Start cooldown period
            await asyncio.sleep(30)
            self._is_toggling = False
            self.async_write_ha_state()
            # Refresh data from the device to get the true state
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn the inverter on."""
        await self._toggle_device(signal="21009", new_state=True)

    async def async_turn_off(self, **kwargs):
        """Turn the inverter off."""
        await self._toggle_device(signal="21010", new_state=False)