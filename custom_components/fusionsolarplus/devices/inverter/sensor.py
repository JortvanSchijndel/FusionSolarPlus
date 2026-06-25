from typing import Dict, Any, List, Set
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import generate_entity_id, EntityCategory
from homeassistant.components.sensor import ENTITY_ID_FORMAT

from ...device_handler import BaseDeviceHandler
from ...entity_naming import (
    configure_sensor_names,
    entity_id_slug,
    pv_api_name,
    signal_entity_id_name,
)
from .const import (
    INVERTER_SIGNALS,
    PV_SIGNALS,
    OPTIMIZER_METRICS,
)


class InverterDeviceHandler(BaseDeviceHandler):
    """Handler for Inverter devices"""

    async def _async_get_data(self) -> Dict[str, Any]:
        async def fetch_inverter_data(client):
            return await self.hass.async_add_executor_job(
                client.get_inverter_data, self.device_id
            )

        return await self._get_client_and_retry(fetch_inverter_data)

    def create_entities(self, coordinator: DataUpdateCoordinator) -> List:
        entities = []
        unique_ids = set()

        # Check output mode to dynamically hide invalid entities
        output_mode = None
        if coordinator.data:
            output_mode = coordinator.data.get("inverter_values", {}).get(21029)

        skip_signal_ids = set()
        if str(output_mode).strip() == "L/N":
            # 10008 is generic grid voltage (now mirrored to 10011)
            # 10012/10013/10015/10016 are Phase B and C metrics
            skip_signal_ids.update([10008, 10012, 10013, 10015, 10016])
        elif str(output_mode).strip() == "Three-phase four-wire system":
            # Three-phase doesn't use the generic single-phase grid voltage entity
            skip_signal_ids.add(10008)

        # Create normal inverter entities
        for signal in INVERTER_SIGNALS:
            signal_id = int(signal["id"])
            if signal_id in skip_signal_ids:
                continue

            unique_id = f"{list(self.device_info['identifiers'])[0][1]}_{signal['id']}"
            if unique_id not in unique_ids:
                api_name = (
                    (coordinator.data or {})
                    .get("inverter_signal_names", {})
                    .get(int(signal["id"]))
                )
                entity = FusionSolarInverterSensor(
                    coordinator,
                    signal["id"],
                    signal["translation_key"],
                    signal.get("unit", None),
                    self.device_info,
                    signal.get("device_class"),
                    signal.get("state_class"),
                    api_name=api_name,
                    entity_id_name=signal_entity_id_name(signal),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

        self._create_pv_entities(coordinator, entities, unique_ids)
        self._create_optimizer_entities(coordinator, entities, unique_ids)

        return entities

    def _create_pv_entities(
        self, coordinator: DataUpdateCoordinator, entities: List, unique_ids: Set[str]
    ):
        if not coordinator.data:
            return

        pv_data = coordinator.data.get("raw_pv_data", {})
        pv_lookup = coordinator.data.get("pv_values", {})
        available_pvs = {pv.lower() for pv in pv_data.get("available_pvs", [])}

        signals_to_input = {
            "PV1": ("11001", "11002", "11003"),
            "PV2": ("11004", "11005", "11006"),
            "PV3": ("11007", "11008", "11009"),
            "PV4": ("11010", "11011", "11012"),
            "PV5": ("11013", "11014", "11015"),
            "PV6": ("11016", "11017", "11018"),
            "PV7": ("11019", "11020", "11021"),
            "PV8": ("11022", "11023", "11024"),
            "PV9": ("11025", "11026", "11027"),
            "PV10": ("11028", "11029", "11030"),
            "PV11": ("11031", "11032", "11033"),
            "PV12": ("11034", "11035", "11036"),
            "PV13": ("11037", "11038", "11039"),
            "PV14": ("11040", "11041", "11042"),
            "PV15": ("11043", "11044", "11045"),
            "PV16": ("11046", "11047", "11048"),
            "PV17": ("11049", "11050", "11051"),
            "PV18": ("11052", "11053", "11054"),
            "PV19": ("11055", "11056", "11057"),
            "PV20": ("11058", "11059", "11060"),
        }

        for pv_name in available_pvs:
            pv_key = pv_name.upper()

            signal_ids = signals_to_input.get(pv_key)
            if not signal_ids:
                continue

            for sig_id in signal_ids:
                pv_signal = next(
                    (ps for ps in PV_SIGNALS if str(ps["id"]) == sig_id), None
                )
                if not pv_signal:
                    continue

                sig_id_int = int(sig_id)
                if sig_id_int not in pv_lookup or pv_lookup[sig_id_int] is None:
                    continue

                unique_id = f"{list(self.device_info['identifiers'])[0][1]}_pv_{sig_id}"
                if unique_id in unique_ids:
                    continue

                entity = FusionSolarInverterSensor(
                    coordinator,
                    int(sig_id),
                    pv_signal["translation_key"],
                    pv_signal["unit"],
                    self.device_info,
                    pv_signal.get("device_class"),
                    pv_signal.get("state_class"),
                    is_pv_signal=True,
                    api_name=pv_api_name(pv_key, pv_signal["translation_key"]),
                    entity_id_name=signal_entity_id_name(pv_signal),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

    def _create_optimizer_entities(
        self, coordinator: DataUpdateCoordinator, entities: List, unique_ids: Set[str]
    ):
        """Create optimizer entities"""
        if not coordinator.data:
            return

        optimizers = coordinator.data.get("raw_optimizer_data", [])
        for optimizer in optimizers:
            optimizer_name = optimizer.get("optName", "Optimizer")
            for metric in OPTIMIZER_METRICS:
                metric_key = metric["name"]
                value = optimizer.get(metric_key)
                if value is not None:
                    unique_id = f"{self.device_id}_{optimizer_name}_{metric_key}"
                    if unique_id not in unique_ids:
                        entity = FusionSolarOptimizerSensor(
                            coordinator,
                            optimizer_name,
                            metric["name"],
                            metric["translation_key"],
                            metric.get("unit"),
                            self.device_info,
                            unique_id,
                            device_class=metric.get("device_class"),
                            state_class=metric.get("state_class"),
                            entity_category=EntityCategory.DIAGNOSTIC,
                            entity_id_name=signal_entity_id_name(metric),
                        )
                        entities.append(entity)
                        unique_ids.add(unique_id)


class FusionSolarInverterSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Inverter devices with daily energy reset handling."""

    def __init__(
        self,
        coordinator,
        signal_id,
        translation_key,
        unit,
        device_info,
        device_class=None,
        state_class=None,
        is_pv_signal=False,
        api_name=None,
        entity_id_name=None,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        configure_sensor_names(self, translation_key=translation_key, api_name=api_name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal

        self._SIGNIFICANT_DROP_FRACTION = 0.25
        self._RESET_NEAR_ZERO_THRESHOLD = 1
        self._last_valid_value = None

        device_id = list(device_info["identifiers"])[0][1]
        slug = entity_id_slug(
            entity_id_name or signal_entity_id_name(api_name=api_name)
        )
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_{slug}",
            hass=coordinator.hass,
        )

    @property
    def native_value(self):
        """Return normalized inverter or PV value from coordinator payload."""
        data = self.coordinator.data
        if not data:
            return None
        if self._is_pv_signal:
            value = data.get("pv_values", {}).get(int(self._signal_id))
        else:
            value = data.get("inverter_values", {}).get(int(self._signal_id))
        if value is None:
            return None
        if self._attr_device_class == SensorDeviceClass.ENUM:
            return str(value)
        if (
            self._attr_state_class == SensorStateClass.TOTAL_INCREASING
            and self._last_valid_value is not None
            and self._last_valid_value > 0
            and value < self._last_valid_value
        ):
            drop_fraction = (self._last_valid_value - value) / self._last_valid_value
            if (
                drop_fraction > self._SIGNIFICANT_DROP_FRACTION
                and value > self._RESET_NEAR_ZERO_THRESHOLD
            ):
                return None
        self._last_valid_value = value
        return value

    @property
    def available(self):
        return bool(self.coordinator.last_update_success and self.coordinator.data)


class FusionSolarOptimizerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Optimizer data."""

    def __init__(
        self,
        coordinator,
        optimizer_name,
        metric_key,
        translation_key,
        unit,
        device_info,
        unique_id,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_id_name=None,
    ):
        super().__init__(coordinator)
        configure_sensor_names(
            self,
            translation_key=translation_key,
            translation_placeholders={"optimizer": optimizer_name},
        )
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = unique_id
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._metric_key = metric_key
        self._optimizer_name = optimizer_name

        device_id = list(device_info["identifiers"])[0][1]
        optimizer_slug = optimizer_name.lower().replace(" ", "_")
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            f"fsp_{device_id}_{optimizer_slug}",
            hass=coordinator.hass,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        optimizer_values = self.coordinator.data.get("optimizer_values", {})
        value = optimizer_values.get(self._optimizer_name, {}).get(self._metric_key)
        if value is None:
            return None
        if self.device_class == SensorDeviceClass.ENUM:
            return str(value)
        return value

    @property
    def available(self):
        return self.coordinator.last_update_success
