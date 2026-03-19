"""
custom_components/fusionsolarplus/devices/charger/select.py
============================================================
SelectEntity : Working Mode (signal id=20002)
  "0" → "Normal charge"
  "1" → "PV Power Preferred"

Lecture depuis le dnId ENFANT (ex: 150468159).
Écriture via elementDn enfant (ex: NE=237145438) — résolu automatiquement par client.
"""

from __future__ import annotations
import logging

from homeassistant.components.select import SelectEntity, ENTITY_ID_FORMAT
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_ID_WORKING_MODE = 20002

WORKING_MODE_OPTIONS = {
    "0": "Normal charge",
    "1": "PV Power Preferred",
}
WORKING_MODE_REVERSE = {v: k for k, v in WORKING_MODE_OPTIONS.items()}


class FusionSolarChargerWorkingModeSelect(CoordinatorEntity, SelectEntity, RestoreEntity):
    """Sélecteur Working Mode (signal 20002 — dnId enfant)."""

    def __init__(self, coordinator, device_info, child_dn_key):
        super().__init__(coordinator)
        self._child_dn_key     = child_dn_key
        self._attr_device_info = device_info
        self._current_key      = "0"
        self._pending_key      = None  # valeur en attente de confirmation API

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
            # Effacer pending seulement quand l'API confirme la nouvelle valeur
            if self._pending_key is not None and api_key == self._pending_key:
                self._pending_key = None
            # Tant que pending est actif, on l'affiche
            if self._pending_key is not None:
                return WORKING_MODE_OPTIONS.get(self._pending_key)
            return WORKING_MODE_OPTIONS.get(api_key, WORKING_MODE_OPTIONS["0"])
        if self._pending_key is not None:
            return WORKING_MODE_OPTIONS.get(self._pending_key)
        return WORKING_MODE_OPTIONS.get(self._current_key)

    async def async_select_option(self, option: str) -> None:
        mode_key = WORKING_MODE_REVERSE.get(option)
        if mode_key is None:
            _LOGGER.error("Working mode inconnu : %s", option)
            return
        device_dn = list(self._attr_device_info["identifiers"])[0][1]
        _LOGGER.debug("Setting working mode %s → %s (%s)", device_dn, option, mode_key)
        # Affichage immédiat, maintenu jusqu'à confirmation API
        self._pending_key = mode_key
        self.async_write_ha_state()
        client = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        await self.hass.async_add_executor_job(
            client.set_charger_working_mode, device_dn, mode_key
        )
        # Pas de refresh immédiat — _pending_key sera effacé quand l'API confirmera

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._current_key = WORKING_MODE_REVERSE.get(last_state.state, "0")


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Setup select platform pour la wallbox."""
    device_info = hass.data[DOMAIN].get(f"{config_entry.entry_id}_device_info")
    coordinator = hass.data[DOMAIN].get(f"{config_entry.entry_id}_config_coordinator")

    if not device_info or not coordinator or not coordinator.data:
        _LOGGER.debug("config_coordinator non disponible pour select (charger)")
        return

    entities = []
    for dn_key, signals in coordinator.data.items():
        if not isinstance(signals, list):
            continue
        if any(s.get("id") == SIGNAL_ID_WORKING_MODE for s in signals):
            entities.append(FusionSolarChargerWorkingModeSelect(
                coordinator=coordinator,
                device_info=device_info,
                child_dn_key=dn_key,
            ))
            break  # un seul sélecteur

    async_add_entities(entities)
