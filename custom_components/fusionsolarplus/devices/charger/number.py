"""Number platform for Charger devices."""

import logging
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    RestoreNumber,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import generate_entity_id

from ...device_handler import BaseDeviceHandler
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_ID_MAX_CHARGE_POWER = 20001
MIN_CHARGE_POWER_KW        = 4.1
MAX_CHARGE_POWER_KW        = 11.0


# ── Handler ───────────────────────────────────────────────────────────────────

class ChargerNumberHandler(BaseDeviceHandler):
    """Handler that fetches charger config and creates Number entities."""

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
            if any(s.get("id") == SIGNAL_ID_MAX_CHARGE_POWER for s in signals):
                entities.append(FusionSolarChargerMaxPowerNumber(
                    coordinator=coordinator,
                    device_info=self.device_info,
                    parent_dn_key=dn_key,
                ))
                break
        return entities


# ── Entity ────────────────────────────────────────────────────────────────────

class FusionSolarChargerMaxPowerNumber(CoordinatorEntity, RestoreNumber):
    """Slider for max charge power (signal 20001 — parent dnId)."""

    def __init__(self, coordinator, device_info, parent_dn_key):
        super().__init__(coordinator)
        self._parent_dn_key     = parent_dn_key
        self._attr_device_info  = device_info
        self._attr_native_value = MAX_CHARGE_POWER_KW
        self._pending_value     = None

        device_id = list(device_info["identifiers"])[0][1]
        self._attr_unique_id                  = f"{device_id}_max_charge_power"
        self._attr_name                       = "Max Charge Power"
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class               = NumberDeviceClass.POWER
        self._attr_mode                       = NumberMode.SLIDER
        self._attr_native_min_value           = MIN_CHARGE_POWER_KW
        self._attr_native_max_value           = MAX_CHARGE_POWER_KW
        self._attr_native_step                = 0.1

        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_max_charge_power",
            hass=coordinator.hass,
        )

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if not data:
            return self._pending_value if self._pending_value is not None else self._attr_native_value
        signals = data.get(self._parent_dn_key, [])
        sig = next((s for s in signals if s.get("id") == SIGNAL_ID_MAX_CHARGE_POWER), None)
        if sig:
            try:
                api_value = float(sig["realValue"])
                self._attr_native_value = api_value
                if self._pending_value is not None and abs(api_value - self._pending_value) < 0.05:
                    self._pending_value = None
                if self._pending_value is not None:
                    return self._pending_value
                return api_value
            except (TypeError, ValueError):
                pass
        return self._pending_value if self._pending_value is not None else self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        device_dn = list(self._attr_device_info["identifiers"])[0][1]
        _LOGGER.debug("Setting max charge power %s → %.1f kW", device_dn, value)
        self._pending_value = value
        self.async_write_ha_state()
        client = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        await self.hass.async_add_executor_job(
            client.set_charger_max_charge_power, device_dn, value
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None:
            self._attr_native_value = last.native_value


# ── Platform setup ────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number platform for Charger devices."""
    device_name = entry.data.get("device_name")
    device_info = hass.data[DOMAIN].get(f"{entry.entry_id}_device_info")

    if not device_info:
        _LOGGER.debug("Device info not found for %s. Skipping number setup.", device_name)
        return

    try:
        handler = ChargerNumberHandler(hass, entry, device_info)
        coordinator = await handler.create_coordinator()
        entities = handler.create_entities(coordinator)
        _LOGGER.info("Adding %d number entities for device %s", len(entities), device_name)
        async_add_entities(entities)
    except Exception as e:
        _LOGGER.error("Failed to set up number entities for device %s: %s", device_name, e)
