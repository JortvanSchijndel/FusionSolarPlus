"""Select platform for Charger devices."""

import logging
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.select import SelectEntity, ENTITY_ID_FORMAT
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.restore_state import RestoreEntity

from ...device_handler import BaseDeviceHandler
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_ID_WORKING_MODE = 20002

WORKING_MODE_OPTIONS = {
    "0": "Normal charge",
    "1": "PV Power Preferred",
}
WORKING_MODE_REVERSE = {v: k for k, v in WORKING_MODE_OPTIONS.items()}


# ── Handler ───────────────────────────────────────────────────────────────────

class ChargerSelectHandler(BaseDeviceHandler):
    """Handler that fetches charger config and creates Select entities."""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch(client):
            return await self.hass.async_add_executor_job(
                client.get_charger_config, self.device_id
            )
        return await self._get_client_and_retry(fetch)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        entities = []
        if not coordinator.data:
            return entities
        for dn_key, signals in coordinator.data.items():
            if not isinstance(signals, list):
                continue
            if any(s.get("id") == SIGNAL_ID_WORKING_MODE for s in signals):
                entities.append(FusionSolarChargerWorkingModeSelect(
                    coordinator=coordinator,
                    device_info=self.device_info,
                    child_dn_key=dn_key,
                ))
                break
        return entities


# ── Entity ────────────────────────────────────────────────────────────────────

class FusionSolarChargerWorkingModeSelect(CoordinatorEntity, SelectEntity, RestoreEntity):
    """Selector for Working Mode (signal 20002 — child dnId)."""

    def __init__(self, coordinator, device_info, child_dn_key):
        super().__init__(coordinator)
        self._child_dn_key     = child_dn_key
        self._attr_device_info = device_info
        self._current_key      = "0"
        self._pending_key      = None

        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id = f"{device_id}_working_mode"
        self._attr_name      = "Working Mode"
        self._attr_options   = list(WORKING_MODE_OPTIONS.values())

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_working_mode",
            hass=coordinator.hass,
        )

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if not data:
            if self._pending_key is not None:
                return WORKING_MODE_OPTIONS.get(self._pending_key)
            return WORKING_MODE_OPTIONS.get(self._current_key)
        signals = data.get(self._child_dn_key, [])
        sig = next((s for s in signals if s.get("id") == SIGNAL_ID_WORKING_MODE), None)
        if sig:
            api_key = sig.get("value", "0")
            self._current_key = api_key
            if self._pending_key is not None and api_key == self._pending_key:
                self._pending_key = None
            if self._pending_key is not None:
                return WORKING_MODE_OPTIONS.get(self._pending_key)
            return WORKING_MODE_OPTIONS.get(api_key, WORKING_MODE_OPTIONS["0"])
        if self._pending_key is not None:
            return WORKING_MODE_OPTIONS.get(self._pending_key)
        return WORKING_MODE_OPTIONS.get(self._current_key)

    async def async_select_option(self, option: str) -> None:
        mode_key = WORKING_MODE_REVERSE.get(option)
        if mode_key is None:
            _LOGGER.error("Unknown working mode: %s", option)
            return
        device_dn = list(self._attr_device_info["identifiers"])[0][1]
        _LOGGER.debug("Setting working mode %s → %s (%s)", device_dn, option, mode_key)
        self._pending_key = mode_key
        self.async_write_ha_state()
        client = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        await self.hass.async_add_executor_job(
            client.set_charger_working_mode, device_dn, mode_key
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._current_key = WORKING_MODE_REVERSE.get(last_state.state, "0")


# ── Platform setup ────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select platform for Charger devices."""
    device_name = entry.data.get("device_name")
    device_info = hass.data[DOMAIN].get(f"{entry.entry_id}_device_info")

    if not device_info:
        _LOGGER.debug("Device info not found for %s. Skipping select setup.", device_name)
        return

    try:
        handler = ChargerSelectHandler(hass, entry, device_info)
        coordinator = await handler.create_coordinator()
        entities = handler.create_entities(coordinator)
        _LOGGER.info("Adding %d select entities for device %s", len(entities), device_name)
        async_add_entities(entities)
    except Exception as e:
        _LOGGER.error("Failed to set up select entities for device %s: %s", device_name, e)
