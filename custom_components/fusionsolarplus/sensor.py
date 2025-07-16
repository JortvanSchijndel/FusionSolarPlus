import logging
import re
import asyncio
from . import DOMAIN
from functools import partial
from datetime import timedelta
from .api.fusion_solar_py.client import FusionSolarClient

from homeassistant.helpers.entity import EntityCategory

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntity,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)

_LOGGER = logging.getLogger(__name__)

# Currency (33 does not exist fsr)
CURRENCY_MAP = {
    1: "CNY",
    2: "USD",
    3: "JPY",
    4: "EUR",
    5: "GBP",
    6: "INR",
    7: "AUD",
    8: "LYD",
    9: "ZAR",
    10: "EGP",
    11: "ARS",
    12: "TRY",
    13: "MXN",
    14: "BRL",
    15: "PESETA",
    16: "CAD",
    17: "KRW",
    18: "MAD",
    19: "CLP",
    20: "PKR",
    21: "SAR",
    22: "THB",
    23: "MYR",
    24: "SGD",
    25: "VND",
    26: "PHP",
    27: "HKD",
    28: "PLN",
    29: "CHF",
    30: "TWD",
    31: "HUF",
    32: "TRY",
    34: "UAH",
    35: "NZD",
    36: "IDR",
    37: "GTQ",
    38: "HNL",
    39: "SVC",
    40: "PAB",
    41: "DOB",
    42: "VEF",
    43: "COP",
    44: "PEN",
    45: "BOB",
    46: "DKK",
    47: "NOK",
    48: "SEK",
    49: "KZT",
    50: "UZS",
}

#
# Define Signals from the API (entities)
#
# Device & state classes: https://developers.home-assistant.io/docs/core/entity/sensor/
INVERTER_SIGNALS = [
    {"id": 10025, "name": "Inverter status", "unit": "", "custom_name": "Status"},
    {"id": 10020, "name": "Power factor", "unit": "", "custom_name": "Power Factor"},
    {"id": 21029, "name": "Output mode", "unit": "", "custom_name": "Output Mode"},
    {
        "id": 10027,
        "name": "Inverter startup time",
        "unit": "",
        "custom_name": "Last Startup Time",
    },
    {
        "id": 10028,
        "name": "Inverter shutdown time",
        "unit": "",
        "custom_name": "Last Shutdown Time",
    },
    {
        "id": 10032,
        "name": "Daily energy",
        "unit": "kWh",
        "custom_name": "Daily Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "id": 10029,
        "name": "Cumulative energy",
        "unit": "kWh",
        "custom_name": "Total Energy Produced",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    {
        "id": 10018,
        "name": "Active power",
        "unit": "kW",
        "custom_name": "Current Active Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10019,
        "name": "Output reactive power",
        "unit": "kvar",
        "custom_name": "Reactive Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10006,
        "name": "Inverter rated power",
        "unit": "kW",
        "custom_name": "Rated Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10021,
        "name": "Grid frequency",
        "unit": "Hz",
        "custom_name": "Grid Frequency",
        "device_class": SensorDeviceClass.FREQUENCY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10014,
        "name": "Grid phase A current",
        "unit": "A",
        "custom_name": "Phase A Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10015,
        "name": "Grid phase B current",
        "unit": "A",
        "custom_name": "Phase B Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10016,
        "name": "Grid phase C current",
        "unit": "A",
        "custom_name": "Phase C Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10011,
        "name": "Phase A voltage",
        "unit": "V",
        "custom_name": "Phase A Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10012,
        "name": "Phase B voltage",
        "unit": "V",
        "custom_name": "Phase B Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10013,
        "name": "Phase C voltage",
        "unit": "V",
        "custom_name": "Phase C Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10023,
        "name": "Internal temperature",
        "unit": "°C",
        "custom_name": "Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10024,
        "name": "Insulation resistance",
        "unit": "MΩ",
        "custom_name": "Insulation Resistance",
    },
]

PV_SIGNALS = [
    {
        "id": 11001,
        "unit": "V",
        "custom_name": "[PV 1] Input Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11004,
        "unit": "V",
        "custom_name": "[PV 2] Input Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11007,
        "unit": "V",
        "custom_name": "[PV 3] Input Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11010,
        "unit": "V",
        "custom_name": "[PV 4] Input Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11002,
        "unit": "A",
        "custom_name": "[PV 1] Input Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11005,
        "unit": "A",
        "custom_name": "[PV 2] Input Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11008,
        "unit": "A",
        "custom_name": "[PV 3] Input Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11011,
        "unit": "A",
        "custom_name": "[PV 4] Input Current",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11003,
        "unit": "W",
        "custom_name": "[PV 1] Input Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11006,
        "unit": "W",
        "custom_name": "[PV 2] Input Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11009,
        "unit": "W",
        "custom_name": "[PV 3] Input Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 11012,
        "unit": "W",
        "custom_name": "[PV 4] Input Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
]

pv_inputs = {
    "pv1": {"voltage": "11001", "current": "11002"},
    "pv2": {"voltage": "11004", "current": "11005"},
    "pv3": {"voltage": "11007", "current": "11008"},
    "pv4": {"voltage": "11010", "current": "11011"},
}


OPTIMIZER_METRICS = [
    {
        "name": "outputPower",
        "custom_name": "Output Power",
        "unit": "W",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "totalEnergy",
        "custom_name": "Total Energy",
        "unit": "kWh",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "name": "inputVoltage",
        "custom_name": "Input Voltage",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "runningStatus",
        "custom_name": "Running Status",
        "unit": None,
        "device_class": None,
        "state_class": None,
    },
    {
        "name": "temperature",
        "custom_name": "Temperature",
        "unit": "°C",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "sn",
        "custom_name": "SN",
        "unit": None,
        "device_class": None,
        "state_class": None,
    },
    {
        "name": "optNumber",
        "custom_name": "Optimizer Number",
        "unit": None,
        "device_class": None,
        "state_class": None,
    },
    {
        "name": "outputVoltage",
        "custom_name": "Output Voltage",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "inputCurrent",
        "custom_name": "Input Current",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
]

PLANT_SIGNALS = [
    {
        "key": "monthEnergy",
        "name": "Monthly Energy",
        "unit": "kWh",
        "custom_name": "Monthly Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "key": "cumulativeEnergy",
        "name": "Cumulative Energy",
        "unit": "kWh",
        "custom_name": "Total Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    {
        "key": "currentPower",
        "name": "Current Power",
        "unit": "kW",
        "custom_name": "Current Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "dailyIncome",
        "name": "Daily Income",
        "unit": "",
        "custom_name": "Today Income",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "key": "dailyEnergy",
        "name": "Daily Energy",
        "unit": "kWh",
        "custom_name": "Today Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "key": "yearEnergy",
        "name": "Yearly Energy",
        "unit": "kWh",
        "custom_name": "Yearly Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
]

BATTERY_STATUS_SIGNALS = [
    {
        "id": 10003,
        "name": "Battery operating status",
        "unit": "",
        "custom_name": "Operating Status",
    },
    {
        "id": 10008,
        "name": "Charge/Discharge mode",
        "unit": "",
        "custom_name": "Charge/Discharge Mode",
    },
    {
        "id": 10013,
        "name": "Rated capacity",
        "unit": "kWh",
        "custom_name": "Rated Capacity",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10015,
        "name": "Backup time",
        "unit": "min",
        "custom_name": "Backup Time",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10001,
        "name": "Energy charged today",
        "unit": "kWh",
        "custom_name": "Energy Charged Today",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "id": 10002,
        "name": "Energy discharged today",
        "unit": "kWh",
        "custom_name": "Energy Discharged Today",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    {
        "id": 10004,
        "name": "Charge/Discharge power",
        "unit": "kW",
        "custom_name": "Charge/Discharge Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10005,
        "name": "Bus voltage",
        "unit": "V",
        "custom_name": "Bus Voltage",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "id": 10006,
        "name": "SOC",
        "unit": "%",
        "custom_name": "State of Charge",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
]

BATTERY_MODULE_SIGNALS_1 = [
    {
        "id": 230320252,
        "name": "[Module 1] No.",
        "unit": "",
        "custom_name": "[Module 1] No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320459,
        "name": "[Module 1] Working Status",
        "unit": "",
        "custom_name": "[Module 1] Working Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320275,
        "name": "[Module 1] SN",
        "unit": "",
        "custom_name": "[Module 1] SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320146,
        "name": "[Module 1] Software Version",
        "unit": "",
        "custom_name": "[Module 1] Software Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320463,
        "name": "[Module 1] SOC",
        "unit": "%",
        "custom_name": "[Module 1] SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320473,
        "name": "[Module 1] Charge and Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 1] Charge and Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320462,
        "name": "[Module 1] Internal Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Internal Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320469,
        "name": "[Module 1] Daily Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Daily Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320470,
        "name": "[Module 1] Daily Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Daily Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320108,
        "name": "[Module 1] Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320460,
        "name": "[Module 1] Bus Voltage",
        "unit": "V",
        "custom_name": "[Module 1] Bus Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320461,
        "name": "[Module 1] Bus Current",
        "unit": "A",
        "custom_name": "[Module 1] Bus Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320514,
        "name": "[Module 1] FE Connection",
        "unit": "",
        "custom_name": "[Module 1] FE Connection",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320107,
        "name": "[Module 1] Total Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Total Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320265,
        "name": "[Module 1] Battery Pack 1 No.",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320266,
        "name": "[Module 1] Battery Pack 2 No.",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320267,
        "name": "[Module 1] Battery Pack 3 No.",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320148,
        "name": "[Module 1] Battery Pack 1 Firmware Version",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320165,
        "name": "[Module 1] Battery Pack 2 Firmware Version",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320181,
        "name": "[Module 1] Battery Pack 3 Firmware Version",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320147,
        "name": "[Module 1] Battery Pack 1 SN",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320164,
        "name": "[Module 1] Battery Pack 2 SN",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320180,
        "name": "[Module 1] Battery Pack 3 SN",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320151,
        "name": "[Module 1] Battery Pack 1 Operating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320168,
        "name": "[Module 1] Battery Pack 2 Operating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320184,
        "name": "[Module 1] Battery Pack 3 Operating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320159,
        "name": "[Module 1] Battery Pack 1 Voltage",
        "unit": "V",
        "custom_name": "[Module 1] Battery Pack 1 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320174,
        "name": "[Module 1] Battery Pack 2 Voltage",
        "unit": "V",
        "custom_name": "[Module 1] Battery Pack 2 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320190,
        "name": "[Module 1] Battery Pack 3 Voltage",
        "unit": "V",
        "custom_name": "[Module 1] Battery Pack 3 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320158,
        "name": "[Module 1] Battery Pack 1 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 1] Battery Pack 1 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320173,
        "name": "[Module 1] Battery Pack 2 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 1] Battery Pack 2 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320189,
        "name": "[Module 1] Battery Pack 3 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 1] Battery Pack 3 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320446,
        "name": "[Module 1] Battery Pack 1 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 1 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320448,
        "name": "[Module 1] Battery Pack 2 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 2 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320450,
        "name": "[Module 1] Battery Pack 3 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 3 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320447,
        "name": "[Module 1] Battery Pack 1 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 1 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320449,
        "name": "[Module 1] Battery Pack 2 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 2 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320451,
        "name": "[Module 1] Battery Pack 3 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 1] Battery Pack 3 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320152,
        "name": "[Module 1] Battery Pack 1 SOC",
        "unit": "%",
        "custom_name": "[Module 1] Battery Pack 1 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320169,
        "name": "[Module 1] Battery Pack 2 SOC",
        "unit": "%",
        "custom_name": "[Module 1] Battery Pack 2 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320185,
        "name": "[Module 1] Battery Pack 3 SOC",
        "unit": "%",
        "custom_name": "[Module 1] Battery Pack 3 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320163,
        "name": "[Module 1] Battery Pack 1 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Battery Pack 1 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320179,
        "name": "[Module 1] Battery Pack 2 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Battery Pack 2 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320194,
        "name": "[Module 1] Battery Pack 3 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 1] Battery Pack 3 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320492,
        "name": "[Module 1] Battery Pack 1 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320493,
        "name": "[Module 1] Battery Pack 2 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320494,
        "name": "[Module 1] Battery Pack 3 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320498,
        "name": "[Module 1] Battery Pack 1 Heating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 1 Heating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320499,
        "name": "[Module 1] Battery Pack 2 Heating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 2 Heating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320500,
        "name": "[Module 1] Battery Pack 3 Heating Status",
        "unit": "",
        "custom_name": "[Module 1] Battery Pack 3 Heating Status",
        "device_class": None,
        "state_class": None,
    },
]

BATTERY_MODULE_SIGNALS_2 = [
    {
        "id": 230320253,
        "name": "[Module 2] No.",
        "unit": "",
        "custom_name": "[Module 2] No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320464,
        "name": "[Module 2] Working Status",
        "unit": "",
        "custom_name": "[Module 2] Working Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320276,
        "name": "[Module 2] SN",
        "unit": "",
        "custom_name": "[Module 2] SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320145,
        "name": "[Module 2] Software Version",
        "unit": "",
        "custom_name": "[Module 2] Software Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320468,
        "name": "[Module 2] SOC",
        "unit": "%",
        "custom_name": "[Module 2] SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320474,
        "name": "[Module 2] Charge and Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 2] Charge and Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320467,
        "name": "[Module 2] Internal Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Internal Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320471,
        "name": "[Module 2] Daily Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Daily Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320472,
        "name": "[Module 2] Daily Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Daily Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320115,
        "name": "[Module 2] Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320465,
        "name": "[Module 2] Bus Voltage",
        "unit": "V",
        "custom_name": "[Module 2] Bus Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320466,
        "name": "[Module 2] Bus Current",
        "unit": "A",
        "custom_name": "[Module 2] Bus Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320515,
        "name": "[Module 2] FE Connection",
        "unit": "",
        "custom_name": "[Module 2] FE Connection",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320114,
        "name": "[Module 2] Total Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Total Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320268,
        "name": "[Module 2] Battery Pack 1 No.",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320269,
        "name": "[Module 2] Battery Pack 2 No.",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320270,
        "name": "[Module 2] Battery Pack 3 No.",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320196,
        "name": "[Module 2] Battery Pack 1 Firmware Version",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320211,
        "name": "[Module 2] Battery Pack 2 Firmware Version",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320226,
        "name": "[Module 2] Battery Pack 3 Firmware Version",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320195,
        "name": "[Module 2] Battery Pack 1 SN",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320210,
        "name": "[Module 2] Battery Pack 2 SN",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320225,
        "name": "[Module 2] Battery Pack 3 SN",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320199,
        "name": "[Module 2] Battery Pack 1 Operating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320214,
        "name": "[Module 2] Battery Pack 2 Operating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320229,
        "name": "[Module 2] Battery Pack 3 Operating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320205,
        "name": "[Module 2] Battery Pack 1 Voltage",
        "unit": "V",
        "custom_name": "[Module 2] Battery Pack 1 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320220,
        "name": "[Module 2] Battery Pack 2 Voltage",
        "unit": "V",
        "custom_name": "[Module 2] Battery Pack 2 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320235,
        "name": "[Module 2] Battery Pack 3 Voltage",
        "unit": "V",
        "custom_name": "[Module 2] Battery Pack 3 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320204,
        "name": "[Module 2] Battery Pack 1 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 2] Battery Pack 1 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320219,
        "name": "[Module 2] Battery Pack 2 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 2] Battery Pack 2 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320234,
        "name": "[Module 2] Battery Pack 3 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 2] Battery Pack 3 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320452,
        "name": "[Module 2] Battery Pack 1 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 1 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320454,
        "name": "[Module 2] Battery Pack 2 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 2 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320456,
        "name": "[Module 2] Battery Pack 3 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 3 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320453,
        "name": "[Module 2] Battery Pack 1 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 1 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320455,
        "name": "[Module 2] Battery Pack 2 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 2 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320457,
        "name": "[Module 2] Battery Pack 3 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 2] Battery Pack 3 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320200,
        "name": "[Module 2] Battery Pack 1 SOC",
        "unit": "%",
        "custom_name": "[Module 2] Battery Pack 1 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320215,
        "name": "[Module 2] Battery Pack 2 SOC",
        "unit": "%",
        "custom_name": "[Module 2] Battery Pack 2 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320230,
        "name": "[Module 2] Battery Pack 3 SOC",
        "unit": "%",
        "custom_name": "[Module 2] Battery Pack 3 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320209,
        "name": "[Module 2] Battery Pack 1 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Battery Pack 1 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320224,
        "name": "[Module 2] Battery Pack 2 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Battery Pack 2 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320239,
        "name": "[Module 2] Battery Pack 3 Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 2] Battery Pack 3 Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320495,
        "name": "[Module 2] Battery Pack 1 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320496,
        "name": "[Module 2] Battery Pack 2 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320497,
        "name": "[Module 2] Battery Pack 3 Battery Health Check",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 Battery Health Check",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320501,
        "name": "[Module 2] Battery Pack 1 Heating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 1 Heating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320502,
        "name": "[Module 2] Battery Pack 2 Heating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 2 Heating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320503,
        "name": "[Module 2] Battery Pack 3 Heating Status",
        "unit": "",
        "custom_name": "[Module 2] Battery Pack 3 Heating Status",
        "device_class": None,
        "state_class": None,
    },
]

BATTERY_MODULE_SIGNALS_3 = [
    {
        "id": 230320640,
        "name": "[Module 3] No.",
        "unit": "",
        "custom_name": "[Module 3] No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320526,
        "name": "[Module 3] Working Status",
        "unit": "",
        "custom_name": "[Module 3] Working Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320536,
        "name": "[Module 3] SN",
        "unit": "",
        "custom_name": "[Module 3] SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320542,
        "name": "[Module 3] Software Version",
        "unit": "",
        "custom_name": "[Module 3] Software Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320529,
        "name": "[Module 3] SOC",
        "unit": "%",
        "custom_name": "[Module 3] SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320527,
        "name": "[Module 3] Charge and Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 3] Charge and Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320535,
        "name": "[Module 3] Internal Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Internal Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320532,
        "name": "[Module 3] Daily Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 3] Daily Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320533,
        "name": "[Module 3] Daily Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 3] Daily Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320539,
        "name": "[Module 3] Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 3] Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320528,
        "name": "[Module 3] Bus Voltage",
        "unit": "V",
        "custom_name": "[Module 3] Bus Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320534,
        "name": "[Module 3] Bus Current",
        "unit": "A",
        "custom_name": "[Module 3] Bus Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320516,
        "name": "[Module 3] FE Connection",
        "unit": "",
        "custom_name": "[Module 3] FE Connection",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320538,
        "name": "[Module 3] Total Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 3] Total Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320646,
        "name": "[Module 3] Battery Pack 1 No.",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 1 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320647,
        "name": "[Module 3] Battery Pack 2 No.",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 2 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320648,
        "name": "[Module 3] Battery Pack 3 No.",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 3 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320544,
        "name": "[Module 3] Battery Pack 1 Firmware Version",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 1 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320555,
        "name": "[Module 3] Battery Pack 2 Firmware Version",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 2 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320566,
        "name": "[Module 3] Battery Pack 3 Firmware Version",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 3 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320543,
        "name": "[Module 3] Battery Pack 1 SN",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 1 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320554,
        "name": "[Module 3] Battery Pack 2 SN",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 2 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320565,
        "name": "[Module 3] Battery Pack 3 SN",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 3 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320545,
        "name": "[Module 3] Battery Pack 1 Operating Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 1 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320556,
        "name": "[Module 3] Battery Pack 2 Operating Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 2 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320567,
        "name": "[Module 3] Battery Pack 3 Operating Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 3 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320549,
        "name": "[Module 3] Battery Pack 1 Voltage",
        "unit": "V",
        "custom_name": "[Module 3] Battery Pack 1 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320560,
        "name": "[Module 3] Battery Pack 2 Voltage",
        "unit": "V",
        "custom_name": "[Module 3] Battery Pack 2 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320571,
        "name": "[Module 3] Battery Pack 3 Voltage",
        "unit": "V",
        "custom_name": "[Module 3] Battery Pack 3 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320548,
        "name": "[Module 3] Battery Pack 1 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 3] Battery Pack 1 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320559,
        "name": "[Module 3] Battery Pack 2 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 3] Battery Pack 2 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320570,
        "name": "[Module 3] Battery Pack 3 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 3] Battery Pack 3 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320576,
        "name": "[Module 3] Battery Pack 1 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 1 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320578,
        "name": "[Module 3] Battery Pack 2 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 2 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320580,
        "name": "[Module 3] Battery Pack 3 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 3 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320577,
        "name": "[Module 3] Battery Pack 1 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 1 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320579,
        "name": "[Module 3] Battery Pack 2 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 2 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320581,
        "name": "[Module 3] Battery Pack 3 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 3] Battery Pack 3 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320546,
        "name": "[Module 3] Battery Pack 1 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 3] Battery Pack 1 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320557,
        "name": "[Module 3] Battery Pack 2 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 3] Battery Pack 2 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320568,
        "name": "[Module 3] Battery Pack 3 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 3] Battery Pack 3 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320552,
        "name": "[Module 3] Battery Pack 1 Current",
        "unit": "A",
        "custom_name": "[Module 3] Battery Pack 1 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320563,
        "name": "[Module 3] Battery Pack 2 Current",
        "unit": "A",
        "custom_name": "[Module 3] Battery Pack 2 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320574,
        "name": "[Module 3] Battery Pack 3 Current",
        "unit": "A",
        "custom_name": "[Module 3] Battery Pack 3 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320553,
        "name": "[Module 3] Battery Pack 1 SOC",
        "unit": "%",
        "custom_name": "[Module 3] Battery Pack 1 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320564,
        "name": "[Module 3] Battery Pack 2 SOC",
        "unit": "%",
        "custom_name": "[Module 3] Battery Pack 2 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320575,
        "name": "[Module 3] Battery Pack 3 SOC",
        "unit": "%",
        "custom_name": "[Module 3] Battery Pack 3 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320504,
        "name": "[Module 3] Battery Pack 1 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 1 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320505,
        "name": "[Module 3] Battery Pack 2 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 2 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320506,
        "name": "[Module 3] Battery Pack 3 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 3] Battery Pack 3 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
]

BATTERY_MODULE_SIGNALS_4 = [
    {
        "id": 230320641,
        "name": "[Module 4] No.",
        "unit": "",
        "custom_name": "[Module 4] No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320583,
        "name": "[Module 4] Working Status",
        "unit": "",
        "custom_name": "[Module 4] Working Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320593,
        "name": "[Module 4] SN",
        "unit": "",
        "custom_name": "[Module 4] SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320599,
        "name": "[Module 4] Software Version",
        "unit": "",
        "custom_name": "[Module 4] Software Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320586,
        "name": "[Module 4] SOC",
        "unit": "%",
        "custom_name": "[Module 4] SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320584,
        "name": "[Module 4] Charge and Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 4] Charge and Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320592,
        "name": "[Module 4] Internal Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Internal Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320589,
        "name": "[Module 4] Daily Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 4] Daily Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320590,
        "name": "[Module 4] Daily Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 4] Daily Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320596,
        "name": "[Module 4] Total Discharge Energy",
        "unit": "kWh",
        "custom_name": "[Module 4] Total Discharge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320585,
        "name": "[Module 4] Bus Voltage",
        "unit": "V",
        "custom_name": "[Module 4] Bus Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320591,
        "name": "[Module 4] Bus Current",
        "unit": "A",
        "custom_name": "[Module 4] Bus Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320517,
        "name": "[Module 4] FE Connection",
        "unit": "",
        "custom_name": "[Module 4] FE Connection",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320595,
        "name": "[Module 4] Total Charge Energy",
        "unit": "kWh",
        "custom_name": "[Module 4] Total Charge Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 230320649,
        "name": "[Module 4] Battery Pack 1 No.",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 1 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320650,
        "name": "[Module 4] Battery Pack 2 No.",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 2 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320651,
        "name": "[Module 4] Battery Pack 3 No.",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 3 No.",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320601,
        "name": "[Module 4] Battery Pack 1 Firmware Version",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 1 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320612,
        "name": "[Module 4] Battery Pack 2 Firmware Version",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 2 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320623,
        "name": "[Module 4] Battery Pack 3 Firmware Version",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 3 Firmware Version",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320600,
        "name": "[Module 4] Battery Pack 1 SN",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 1 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320611,
        "name": "[Module 4] Battery Pack 2 SN",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 2 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320622,
        "name": "[Module 4] Battery Pack 3 SN",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 3 SN",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320602,
        "name": "[Module 4] Battery Pack 1 Operating Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 1 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320613,
        "name": "[Module 4] Battery Pack 2 Operating Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 2 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320624,
        "name": "[Module 4] Battery Pack 3 Operating Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 3 Operating Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320606,
        "name": "[Module 4] Battery Pack 1 Voltage",
        "unit": "V",
        "custom_name": "[Module 4] Battery Pack 1 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320617,
        "name": "[Module 4] Battery Pack 2 Voltage",
        "unit": "V",
        "custom_name": "[Module 4] Battery Pack 2 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320628,
        "name": "[Module 4] Battery Pack 3 Voltage",
        "unit": "V",
        "custom_name": "[Module 4] Battery Pack 3 Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 230320605,
        "name": "[Module 4] Battery Pack 1 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 4] Battery Pack 1 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320616,
        "name": "[Module 4] Battery Pack 2 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 4] Battery Pack 2 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320627,
        "name": "[Module 4] Battery Pack 3 Charge/Discharge Power",
        "unit": "kW",
        "custom_name": "[Module 4] Battery Pack 3 Charge/Discharge Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 230320633,
        "name": "[Module 4] Battery Pack 1 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 1 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320635,
        "name": "[Module 4] Battery Pack 2 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 2 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320637,
        "name": "[Module 4] Battery Pack 3 Maximum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 3 Maximum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320634,
        "name": "[Module 4] Battery Pack 1 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 1 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320636,
        "name": "[Module 4] Battery Pack 2 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 2 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320638,
        "name": "[Module 4] Battery Pack 3 Minimum Temperature",
        "unit": "°C",
        "custom_name": "[Module 4] Battery Pack 3 Minimum Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "id": 230320603,
        "name": "[Module 4] Battery Pack 1 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 4] Battery Pack 1 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320614,
        "name": "[Module 4] Battery Pack 2 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 4] Battery Pack 2 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320625,
        "name": "[Module 4] Battery Pack 3 Capacity",
        "unit": "Ah",
        "custom_name": "[Module 4] Battery Pack 3 Capacity",
        "device_class": None,
        "state_class": "measurement",
    },
    {
        "id": 230320609,
        "name": "[Module 4] Battery Pack 1 Current",
        "unit": "A",
        "custom_name": "[Module 4] Battery Pack 1 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320620,
        "name": "[Module 4] Battery Pack 2 Current",
        "unit": "A",
        "custom_name": "[Module 4] Battery Pack 2 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320631,
        "name": "[Module 4] Battery Pack 3 Current",
        "unit": "A",
        "custom_name": "[Module 4] Battery Pack 3 Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 230320610,
        "name": "[Module 4] Battery Pack 1 SOC",
        "unit": "%",
        "custom_name": "[Module 4] Battery Pack 1 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320621,
        "name": "[Module 4] Battery Pack 2 SOC",
        "unit": "%",
        "custom_name": "[Module 4] Battery Pack 2 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320632,
        "name": "[Module 4] Battery Pack 3 SOC",
        "unit": "%",
        "custom_name": "[Module 4] Battery Pack 3 SOC",
        "device_class": "battery",
        "state_class": "measurement",
    },
    {
        "id": 230320507,
        "name": "[Module 4] Battery Pack 1 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 1 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320508,
        "name": "[Module 4] Battery Pack 2 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 2 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
    {
        "id": 230320509,
        "name": "[Module 4] Battery Pack 3 High Voltage Fuse Status",
        "unit": "",
        "custom_name": "[Module 4] Battery Pack 3 High Voltage Fuse Status",
        "device_class": None,
        "state_class": None,
    },
]

MODULE_SIGNAL_MAP = {
    "1": BATTERY_MODULE_SIGNALS_1,
    "2": BATTERY_MODULE_SIGNALS_2,
    "3": BATTERY_MODULE_SIGNALS_3,
    "4": BATTERY_MODULE_SIGNALS_4,
}

POWER_SENSOR_SIGNALS = [
    {
        "id": 10001,
        "name": "Meter status",
        "unit": "",
        "custom_name": "Meter Status",
    },
    {
        "id": 10008,
        "name": "Positive active energy",
        "unit": "kWh",
        "custom_name": "Positive Active Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 10009,
        "name": "Negative active energy",
        "unit": "kWh",
        "custom_name": "Negative Active Energy",
        "device_class": "energy",
        "state_class": "total_increasing",
    },
    {
        "id": 10005,
        "name": "Reactive power",
        "unit": "Var",
        "custom_name": "Reactive Power",
        "device_class": "reactive_power",
        "state_class": "measurement",
    },
    {
        "id": 10004,
        "name": "Active power",
        "unit": "W",
        "custom_name": "Active Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 10006,
        "name": "Power factor",
        "unit": "",
        "custom_name": "Power Factor",
        "device_class": "power_factor",
        "state_class": "measurement",
    },
    {
        "id": 10019,
        "name": "Phase A active power",
        "unit": "W",
        "custom_name": "Phase A Active Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 10020,
        "name": "Phase B active power",
        "unit": "W",
        "custom_name": "Phase B Active Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 10021,
        "name": "Phase C active power",
        "unit": "W",
        "custom_name": "Phase C Active Power",
        "device_class": "power",
        "state_class": "measurement",
    },
    {
        "id": 10002,
        "name": "Phase A voltage",
        "unit": "V",
        "custom_name": "Phase A Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 10010,
        "name": "Phase B voltage",
        "unit": "V",
        "custom_name": "Phase B Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 10011,
        "name": "Phase C voltage",
        "unit": "V",
        "custom_name": "Phase C Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
    },
    {
        "id": 10003,
        "name": "Phase A current",
        "unit": "A",
        "custom_name": "Phase A Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 10012,
        "name": "Phase B current",
        "unit": "A",
        "custom_name": "Phase B Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 10013,
        "name": "Phase C current",
        "unit": "A",
        "custom_name": "Phase C Current",
        "device_class": "current",
        "state_class": "measurement",
    },
    {
        "id": 10007,
        "name": "Grid frequency",
        "unit": "Hz",
        "custom_name": "Grid Frequency",
        "device_class": "frequency",
        "state_class": "measurement",
    },
]


async def async_setup_entry(hass, entry, async_add_entities):
    device_type = entry.data.get("device_type")
    device_id = entry.data.get("device_id")
    device_name = entry.data.get("device_name")

    device_info = {
        "identifiers": {(DOMAIN, str(device_id))},
        "name": device_name,
        "manufacturer": "FusionSolar",
        "model": device_type or "Unknown",
        "via_device": None,
    }

    async def async_get_data():
        client = hass.data[DOMAIN][entry.entry_id]
        username = entry.data["username"]
        password = entry.data["password"]
        subdomain = entry.data.get("subdomain", "uni001eu5")

        async def ensure_logged_in(client_instance):
            try:
                is_active = await hass.async_add_executor_job(
                    client_instance.is_session_active
                )
                if not is_active:
                    await hass.async_add_executor_job(client_instance._login)

                    is_active = await hass.async_add_executor_job(
                        client_instance.is_session_active
                    )
                    if not is_active:
                        raise Exception("Login completed but session still not active")

                return True
            except Exception:
                return False

        async def create_new_client():
            new_client = await hass.async_add_executor_job(
                partial(
                    FusionSolarClient,
                    username,
                    password,
                    captcha_model_path=hass,
                    huawei_subdomain=subdomain,
                )
            )

            if await hass.async_add_executor_job(new_client.is_session_active):
                hass.data[DOMAIN][entry.entry_id] = new_client
                return new_client
            return None

        if not await ensure_logged_in(client):
            client = await create_new_client()

        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                if device_type == "Inverter" or device_type == "Power Sensor":
                    response = await hass.async_add_executor_job(
                        client.get_real_time_data, device_id
                    )

                    optimizer_stats = await hass.async_add_executor_job(
                        client.get_optimizer_stats, device_id
                    )

                    response["optimizers"] = optimizer_stats

                    pv_stats_raw = await hass.async_add_executor_job(
                        client.get_pv_info, device_id
                    )

                    signals = (
                        pv_stats_raw.get("signals", {})
                        if isinstance(pv_stats_raw, dict)
                        else {}
                    )

                    normalized_pv = [
                        {"id": str(signal_id), "value": data.get("value")}
                        for signal_id, data in signals.items()
                        if data.get("value") is not None
                    ]
                    response["pv"] = normalized_pv
                elif device_type == "Plant":
                    response = await hass.async_add_executor_job(
                        client.get_current_plant_data, device_id
                    )
                elif device_type == "Battery":
                    response = await hass.async_add_executor_job(
                        client.get_battery_status, device_id
                    )
                    module_data = {}
                    for module_id in ["1", "2", "3", "4"]:
                        stats = await hass.async_add_executor_job(
                            client.get_battery_module_stats, device_id, module_id
                        )
                        if stats:
                            module_data[module_id] = stats
                    response = {"battery": response, "modules": module_data}

                else:
                    raise Exception("Unsupported device type")

                if response is None:
                    raise Exception("API returned None response")

                return response

            except Exception as err:
                if attempt < max_retries:
                    recovery_success = False

                    try:
                        await hass.async_add_executor_job(client._login)

                        if await hass.async_add_executor_job(client.is_session_active):
                            recovery_success = True
                        return None

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
                    raise UpdateFailed(
                        f"Error fetching data after {max_retries + 1} attempts: {err}"
                    )

        raise UpdateFailed("Unexpected end of retry loop")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{device_name} FusionSolar Data",
        update_method=async_get_data,
        update_interval=timedelta(seconds=15),
    )

    await coordinator.async_config_entry_first_refresh()

    if device_type == "Inverter":
        signals = INVERTER_SIGNALS
        id_key = "id"
        entity_class = FusionSolarInverterSensor
    elif device_type == "Plant":
        signals = PLANT_SIGNALS
        id_key = "key"
        entity_class = FusionSolarPlantSensor
    elif device_type == "Battery":
        signals = BATTERY_STATUS_SIGNALS
        id_key = "id"
        entity_class = FusionSolarBatterySensor
    elif device_type == "Power Sensor":
        signals = POWER_SENSOR_SIGNALS
        id_key = "id"
        entity_class = FusionSolarPowerSensor
    else:
        _LOGGER.error("Unknown device type: %s", device_type)
        return

    unique_ids = set()
    entities = []

    for signal in signals:
        unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal[id_key]}"
        if unique_id not in unique_ids:
            entity = entity_class(
                coordinator,
                signal[id_key],
                signal.get("custom_name", signal["name"]),
                signal["unit"],
                device_info,
                signal.get("device_class"),
                signal.get("state_class"),
            )
            entities.append(entity)
            unique_ids.add(unique_id)

    # Add PV entities for inverters
    if device_type == "Inverter":
        pv_data = coordinator.data.get("pv", []) if coordinator.data else []

        pv_lookup = {
            item["id"]: item["value"]
            for item in pv_data
            if "id" in item and "value" in item
        }

        active_pvs = set()
        for pv_name, ids in pv_inputs.items():
            voltage_str = pv_lookup.get(ids["voltage"])
            current_str = pv_lookup.get(ids["current"])

            try:
                voltage = float(voltage_str)
            except (ValueError, TypeError):
                voltage = 0.0

            try:
                current = float(current_str)
            except (ValueError, TypeError):
                current = 0.0

            if voltage > 0 or current > 0:
                active_pvs.add(pv_name)

        signal_to_pv_input = {
            "11001": "pv1",
            "11002": "pv1",
            "11003": "pv1",
            "11004": "pv2",
            "11005": "pv2",
            "11006": "pv2",
            "11007": "pv3",
            "11008": "pv3",
            "11009": "pv3",
            "11010": "pv4",
            "11011": "pv4",
            "11012": "pv4",
        }

        for pv_signal in PV_SIGNALS:
            pv_id = str(pv_signal["id"])
            pv_input = signal_to_pv_input.get(pv_id)

            if pv_input not in active_pvs:
                _LOGGER.debug(
                    "Skipping %s because its voltage and current are 0", pv_input
                )
                continue

            has_data = any(
                str(pv_item.get("id")) == pv_id and pv_item.get("value") is not None
                for pv_item in pv_data
            )

            if has_data:
                unique_id = (
                    f"{list(device_info['identifiers'])[0][1]}_pv_{pv_signal['id']}"
                )
                if unique_id not in unique_ids:
                    entity = FusionSolarInverterSensor(
                        coordinator,
                        pv_signal["id"],
                        pv_signal["custom_name"],
                        pv_signal["unit"],
                        device_info,
                        pv_signal.get("device_class"),
                        pv_signal.get("state_class"),
                        is_pv_signal=True,
                    )
                    entities.append(entity)
                    unique_ids.add(unique_id)

    modules_data = coordinator.data.get("modules", {}) if coordinator.data else {}
    for module_id, module_signals in MODULE_SIGNAL_MAP.items():
        module_signals_data = modules_data.get(module_id)
        if not module_signals_data:
            continue

        valid_packs = set()
        for signal in module_signals_data:
            name = signal.get("name", "")
            match = re.search(r"\[Battery pack (\d+)\] SN", name, re.IGNORECASE)
            if match and signal.get("realValue"):
                valid_packs.add(match.group(1))

        for signal in module_signals:
            name = signal.get("name", "")
            pack_match = re.search(r"Battery pack (\d+)", name, re.IGNORECASE)
            if pack_match:
                pack_no = pack_match.group(1)
                if pack_no not in valid_packs:
                    continue

            unique_id = f"{list(device_info['identifiers'])[0][1]}_module{module_id}_{signal['id']}"
            if unique_id not in unique_ids:
                entity = FusionSolarBatteryModuleSensor(
                    coordinator,
                    signal["id"],
                    signal.get("custom_name", signal["name"]),
                    signal["unit"],
                    device_info,
                    module_id,
                    signal.get("device_class"),
                    signal.get("state_class"),
                )
                entities.append(entity)
                unique_ids.add(unique_id)

    optimizers = (
        coordinator.data["optimizers"]
        if coordinator.data and "optimizers" in coordinator.data
        else []
    )
    for optimizer in optimizers:
        optimizer_name = optimizer.get("optName", "Optimizer")
        for metric in OPTIMIZER_METRICS:
            metric_key = metric["name"]
            value = optimizer.get(metric_key)
            if value is not None:
                unique_id = f"{device_id}_{optimizer_name}_{metric_key}"
                entity = FusionSolarOptimizerSensor(
                    coordinator,
                    optimizer_name,
                    metric["name"],
                    metric.get("custom_name", metric["name"]),
                    metric.get("unit"),
                    device_info,
                    unique_id,
                    device_class=metric.get("device_class"),
                    state_class=metric.get("state_class"),
                    entity_category=EntityCategory.DIAGNOSTIC,
                )
                entities.append(entity)

    _LOGGER.error("Adding %d entities for device %s", len(entities), device_name)
    async_add_entities(entities)


#
#   Inverter
#
class FusionSolarInverterSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
        is_pv_signal=False,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._is_pv_signal = is_pv_signal

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None

        # Handle PV signals
        if self._is_pv_signal:
            pv_data = data.get("pv", [])  # now this is a list
            for item in pv_data:
                if str(item.get("id")) == str(self._signal_id):
                    value = item.get("value")
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return value
            return None

        # Handle regular inverter signals
        for group in data.get("data", []):
            if "signals" in group:
                for signal in group["signals"]:
                    if signal["id"] == self._signal_id:
                        value = signal.get("value")
                        if value is not None:
                            if signal.get("unit"):
                                try:
                                    return float(value)
                                except (TypeError, ValueError):
                                    return None
                            else:
                                return value
        return None

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


class FusionSolarOptimizerSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        optimizer_name,
        metric_key,
        custom_name,
        unit,
        device_info,
        unique_id,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ):
        super().__init__(coordinator)
        self._attr_name = f"[{optimizer_name}] {custom_name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = unique_id
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._metric_key = metric_key
        self._optimizer_name = optimizer_name

    @property
    def state(self):
        data = (
            self.coordinator.data.get("optimizers", []) if self.coordinator.data else []
        )
        for opt in data:
            if opt.get("optName") == self._optimizer_name:
                value = opt.get(self._metric_key)
                if value is not None and isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                return value
        return None

    @property
    def available(self):
        return self.coordinator.last_update_success


#
#   Plant
#


class FusionSolarPlantSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        key,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
    ):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._base_unit = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{key}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_unit_of_measurement(self):
        # set currency unit dynamically from api
        if self._key == "dailyIncome":
            data = self.coordinator.data
            if data:
                currency_num = data.get("currency")
                if currency_num:
                    return CURRENCY_MAP.get(currency_num, str(currency_num))
        return self._base_unit

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None
        value = data.get(self._key)
        if value is None:
            return None
        if self.native_unit_of_measurement:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        else:
            return value

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


#
#   Battery
#


class FusionSolarBatterySensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None

        signals = data.get("battery", [])
        if not signals:
            return None

        for signal in signals:
            if signal["id"] == self._signal_id:
                if signal.get("unit"):
                    try:
                        return float(signal.get("value"))
                    except (TypeError, ValueError):
                        return None
                else:
                    return signal.get("value")
        return None

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


class FusionSolarBatteryModuleSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        module_id,
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{list(device_info['identifiers'])[0][1]}_module{module_id}_{signal_id}"
        )
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._module_id = module_id

    @property
    def state(self):
        data = self.coordinator.data
        if not data or "modules" not in data:
            return None
        module_signals = data["modules"].get(self._module_id, [])
        for signal in module_signals:
            if signal["id"] == self._signal_id:
                try:
                    return float(signal.get("realValue"))
                except (TypeError, ValueError):
                    return signal.get("realValue")
        return None

    @property
    def available(self):
        data = self.coordinator.data
        return (
            self.coordinator.last_update_success
            and data is not None
            and "modules" in data
            and self._module_id in data["modules"]
            and bool(data["modules"][self._module_id])
        )


#
#   Power Sensor
#


class FusionSolarPowerSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        signal_id,
        name,
        unit,
        device_info,
        device_class=None,
        state_class=None,
    ):
        super().__init__(coordinator)
        self._signal_id = signal_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info
        self._attr_unique_id = f"{list(device_info['identifiers'])[0][1]}_{signal_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def state(self):
        data = self.coordinator.data
        if not data:
            return None
        for group in data.get("data", []):
            if "signals" in group:
                for signal in group["signals"]:
                    if signal["id"] == self._signal_id:
                        if signal.get("unit"):
                            try:
                                return float(signal.get("value"))
                            except (TypeError, ValueError):
                                return None
                        else:
                            return signal.get("value")
        return None

    @property
    def available(self):
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
