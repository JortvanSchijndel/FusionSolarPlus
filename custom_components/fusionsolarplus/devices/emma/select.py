"""Select platform for EMMA/SmartAssistant devices."""

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

SIGNAL_ID_PV_POWER_PRIORITY = 230700180

PV_PRIORITY_OPTIONS = {
    "0": "Battery first",
    "1": "Appliances first",
}
PV_PRIORITY_REVERSE = {v: k for k, v in PV_PRIORITY_OPTIONS.items()}


# ── Handler ───────────────────────────────────────────────────────────────────

class EMMASelectHandler(BaseDeviceHandler):
    """Handler that fetches EMMA/SmartAssistant config and creates Select entities."""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch(client):
            return await self.hass.async_add_executor_job(
                client.get_smart_assistant_config, self.device_id
            )
        return await self._get_client_and_retry(fetch)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> list:
        entities = []
        if not coordinator.data:
            return entities
        for dn_key, signals in coordinator.data.items():
            if not isinstance(signals, list):
                continue
            if any(s.get("id") == SIGNAL_ID_PV_POWER_PRIORITY for s in signals):
                entities.append(FusionSolarEMMAPvPrioritySelect(
                    coordinator=coordinator,
                    device_info=self.device_info,
                    dn_key=dn_key,
                ))
                break
        return entities


# ── Entity ────────────────────────────────────────────────────────────────────

class FusionSolarEMMAPvPrioritySelect(CoordinatorEntity, SelectEntity, RestoreEntity):
    """Selector for PV Power Priority / Battery First (signal 230700180)."""

    def __init__(self, coordinator, device_info, dn_key):
        super().__init__(coordinator)
        self._dn_key           = dn_key
        self._attr_device_info = device_info
        self._current_key      = "0"
        self._pending_key      = None

        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id = f"{device_id}_pv_power_priority"
        self._attr_name      = "PV Power Priority"
        self._attr_options   = list(PV_PRIORITY_OPTIONS.values())

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_pv_power_priority",
            hass=coordinator.hass,
        )

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if not data:
            if self._pending_key is not None:
                return PV_PRIORITY_OPTIONS.get(self._pending_key)
            return PV_PRIORITY_OPTIONS.get(self._current_key)
        signals = data.get(self._dn_key, [])
        sig = next((s for s in signals if s.get("id") == SIGNAL_ID_PV_POWER_PRIORITY), None)
        if sig:
            api_key = sig.get("value", "0")
            self._current_key = api_key
            if self._pending_key is not None and api_key == self._pending_key:
                self._pending_key = None
            if self._pending_key is not None:
                return PV_PRIORITY_OPTIONS.get(self._pending_key)
            return PV_PRIORITY_OPTIONS.get(api_key, PV_PRIORITY_OPTIONS["0"])
        if self._pending_key is not None:
            return PV_PRIORITY_OPTIONS.get(self._pending_key)
        return PV_PRIORITY_OPTIONS.get(self._current_key)

    async def async_select_option(self, option: str) -> None:
        priority_key = PV_PRIORITY_REVERSE.get(option)
        if priority_key is None:
            _LOGGER.error("Unknown PV Power Priority option: %s", option)
            return
        device_dn = list(self._attr_device_info["identifiers"])[0][1]
        _LOGGER.debug("Setting PV Power Priority %s → %s (%s)", device_dn, option, priority_key)
        self._pending_key = priority_key
        self.async_write_ha_state()
        client = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        await self.hass.async_add_executor_job(
            client.set_smart_assistant_pv_priority, device_dn, priority_key
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._current_key = PV_PRIORITY_REVERSE.get(last_state.state, "0")


# ── Platform setup ────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up select platform for EMMA/SmartAssistant devices."""
    device_name = entry.data.get("device_name")
    device_info = hass.data[DOMAIN].get(f"{entry.entry_id}_device_info")

    if not device_info:
        _LOGGER.debug("Device info not found for %s. Skipping select setup.", device_name)
        return

    try:
        handler = EMMASelectHandler(hass, entry, device_info)
        coordinator = await handler.create_coordinator()
        entities = handler.create_entities(coordinator)
        _LOGGER.info("Adding %d select entities for device %s", len(entities), device_name)
        async_add_entities(entities)
    except Exception as e:
        _LOGGER.error("Failed to set up select entities for device %s: %s", device_name, e)
