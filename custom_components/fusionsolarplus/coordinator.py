from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from fusion_solar_py.client import FusionSolarClient
from .const import CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_IDS

class FusionSolarCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(hass, _LOGGER, name="FusionSolarPlus", update_interval=timedelta(minutes=1))

        self.client = FusionSolarClient(config[CONF_USERNAME], config[CONF_PASSWORD])
        self.device_ids = [d.strip() for d in config[CONF_DEVICE_IDS].split(",")]

    async def _async_update_data(self):
        data = {}
        for device_id in self.device_ids:
            response = await self.hass.async_add_executor_job(
                self.client.get_real_time_data, f"NE={device_id}"
            )
            data[device_id] = response
        return data
