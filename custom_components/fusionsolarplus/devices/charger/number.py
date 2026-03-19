"""
custom_components/fusionsolarplus/devices/charger/number.py
============================================================
NumberEntity : Limite supérieure de puissance de charge (signal id=20001)
Lecture depuis le dnId PARENT (ex: 150453477), écriture via device_dn parent.
"""

from __future__ import annotations
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    RestoreNumber,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_ID_MAX_CHARGE_POWER = 20001
MIN_CHARGE_POWER_KW        = 4.1
MAX_CHARGE_POWER_KW        = 11.0


class FusionSolarChargerMaxPowerNumber(CoordinatorEntity, RestoreNumber):
    """Slider pour la limite de puissance de charge (signal 20001 — dnId parent)."""

    def __init__(self, coordinator, device_info, parent_dn_key):
        super().__init__(coordinator)
        self._parent_dn_key     = parent_dn_key
        self._attr_device_info  = device_info
        self._attr_native_value = MAX_CHARGE_POWER_KW
        self._pending_value     = None  # valeur en attente de confirmation API

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
                # Effacer pending seulement quand l'API confirme la nouvelle valeur
                if self._pending_value is not None and abs(api_value - self._pending_value) < 0.05:
                    self._pending_value = None
                # Tant que pending est actif, on l'affiche
                if self._pending_value is not None:
                    return self._pending_value
                return api_value
            except (TypeError, ValueError):
                pass
        return self._pending_value if self._pending_value is not None else self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        device_dn = list(self._attr_device_info["identifiers"])[0][1]
        _LOGGER.debug("Setting max charge power %s → %.1f kW", device_dn, value)
        # Affichage immédiat, maintenu jusqu'à confirmation API
        self._pending_value = value
        self.async_write_ha_state()
        client = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        await self.hass.async_add_executor_job(
            client.set_charger_max_charge_power, device_dn, value
        )
        # Pas de refresh immédiat — le coordinator rafraîchira au prochain cycle (30s)
        # _pending_value sera effacé quand l'API confirmera la nouvelle valeur

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None:
            self._attr_native_value = last.native_value


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Setup number platform pour la wallbox."""
    device_info = hass.data[DOMAIN].get(f"{config_entry.entry_id}_device_info")
    coordinator = hass.data[DOMAIN].get(f"{config_entry.entry_id}_config_coordinator")

    if not device_info or not coordinator or not coordinator.data:
        _LOGGER.debug("config_coordinator non disponible pour number (charger)")
        return

    entities = []
    for dn_key, signals in coordinator.data.items():
        if not isinstance(signals, list):
            continue
        if any(s.get("id") == SIGNAL_ID_MAX_CHARGE_POWER for s in signals):
            entities.append(FusionSolarChargerMaxPowerNumber(
                coordinator=coordinator,
                device_info=device_info,
                parent_dn_key=dn_key,
            ))
            break  # un seul slider suffit

    async_add_entities(entities)
