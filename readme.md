
![Logo](https://raw.githubusercontent.com/JortvanSchijndel/FusionSolarPlus/refs/heads/master/branding/logo.png)

<table align="center" border="0">
  <tr>
    <td align="center">
      <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=JortvanSchijndel&repository=FusionSolarPlus&category=Integration">
        <img alt="Total Downloads" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.fusionsolarplus.total&logo=homeassistantcommunitystore&logoColor=%235c5c5c&label=Total%20Downloads&labelColor=%23ffffff&color=%234983FF&cacheSeconds=600">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/JortvanSchijndel/FusionSolarPlus/releases">
        <img alt="GitHub Release" src="https://img.shields.io/github/v/release/JortvanSchijndel/FusionSolarPlus?display_name=release&logo=V&logoColor=%235c5c5c&label=Latest%20Version&labelColor=%23ffffff&color=%234983FF&cacheSeconds=600">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/JortvanSchijndel/FusionSolarPlus/actions/workflows/lint.yml">
        <img alt="Lint Workflow" src="https://img.shields.io/github/actions/workflow/status/JortvanSchijndel/FusionSolarPlus/lint.yml?logo=testcafe&logoColor=%235c5c5c&label=Lint%20Workflow&labelColor=%23ffffff&color=%234983FF&cacheSeconds=600">
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/JortvanSchijndel/FusionSolarPlus/actions/workflows/validate.yml">
        <img alt="Hassfest & HACS Validation Workflow" src="https://img.shields.io/github/actions/workflow/status/JortvanSchijndel/FusionSolarPlus/validate.yml?logo=testcafe&logoColor=%235c5c5c&label=Hassfest%20%26%20HACS%20Validation%20Workflow&labelColor=%23ffffff&color=%234983FF&cacheSeconds=600">
      </a>
    </td>
  </tr>
</table>

---

# FusionSolarPlus
This integration brings full FusionSolar support to Home Assistant, with entities for plants, inverters, and more. It authenticates using your FusionSolar username and password. No northbound API, OpenAPI, or kiosk URL required. I originally built it as a custom Python script that sent data via MQTT, but realizing others might want a Home Assistant integration with full entity support, I ported it with AI assistance into a proper integration for easier use.

## Setup
Click the button below and download the FusionSolarPlus integration.

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=JortvanSchijndel&repository=FusionSolarPlus&category=Integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

Once installed:

1. Restart Home Assistant and head over to **Settings » Devices & Services.**  
2. Click on **"Add Integration."**  
3. Search for **"FusionSolarPlus."**  
4. Enter your FusionSolar username, password and subdomain. (For a list For a list of available subdomains click [here](https://support.huawei.com/enterprise/en/doc/EDOC1100165054/dbeb5df3/domain-name-list-of-management-systems). eg. 'region01eu5)  
5. Select the device type you want to add, then choose the specific device.

# Entities

## Plant
|Entity         |Unit       |
----------------|:------------:
|Current Power  |kW         |
|Today Energy   |kWh        |
|Montly Energy  |kWh        |
|Yearly Energy  |kWh        |
|Total Energy   |kWh        |
|Today Income   |[ISO 4217](https://en.wikipedia.org/wiki/ISO_4217#Active_codes) |

## Inverter
| Entity                 | Unit     |
|------------------------|:--------:|
| Current Active Power   | kW       |
| Daily Energy           | kWh      |
| Grid Frequency         | Hz       |
| Insulation Resistance  | MΩ       |
| Last Shutdown Time     | Datetime |
| Last Startup Time      | Datetime |
| Output Mode            | Text     |
| Phase A Current        | A        |
| Phase A Voltage        | V        |
| Phase B Current        | A        |
| Phase B Voltage        | V        |
| Phase C Current        | A        |
| Phase C Voltage        | V        |
| Power Factor           | Ratio    |
| Rated Power            | kW       |
| Reactive Power         | kvar     |
| Status                 | Text     |
| Temperature            | °C       |
| Total Energy Produced  | kWh      |

## Optimizer

| Entity             | Unit   |
|--------------------|:------:|
| Output Power       | W      |
| Total Energy       | kWh    |
| Input Voltage      | V      |
| Running Status     | Text   |
| Temperature        | °C     |
| Serial Number (SN) | Text   |
| Optimizer Number   | Text   |
| Output Voltage     | V      |
| Input Current      | A      |


## Battery
| Entity                                        | Unit     |
|-----------------------------------------------|:--------:|
| Operating Status                             | Text     |
| Charge/Discharge Mode                        | Text     |
| Rated Capacity                               | kWh      |
| Backup Time                                  | min      |
| Energy Charged Today                         | kWh      |
| Energy Discharged Today                      | kWh      |
| Charge/Discharge Power                       | kW       |
| Bus Voltage                                  | V        |
| State of Charge                              | %        |
| [Module X] No.                                          | Text     |
| [Module X] Working Status                               | Text     |
| [Module X] SN                                           | Text     |
| [Module X] Software Version                             | Text     |
| [Module X] SOC                                          | %        |
| [Module X] Charge and Discharge Power                   | kW       |
| [Module X] Internal Temperature                         | °C       |
| [Module X] Daily Charge Energy                          | kWh      |
| [Module X] Daily Discharge Energy                       | kWh      |
| [Module X] Total Discharge Energy                       | kWh      |
| [Module X] Bus Voltage                                  | V        |
| [Module X] Bus Current                                  | A        |
| [Module X] FE Connection                                | Text     |
| [Module X] Total Charge Energy                          | kWh      |
| [Module X] Battery Pack 1 No.                          | Text     |
| [Module X] Battery Pack 2 No.                          | Text     |
| [Module X] Battery Pack 3 No.                          | Text     |
| [Module X] Battery Pack 1 Firmware Version             | Text     |
| [Module X] Battery Pack 2 Firmware Version             | Text     |
| [Module X] Battery Pack 3 Firmware Version             | Text     |
| [Module X] Battery Pack 1 SN                           | Text     |
| [Module X] Battery Pack 2 SN                           | Text     |
| [Module X] Battery Pack 3 SN                           | Text     |
| [Module X] Battery Pack 1 Operating Status             | Text     |
| [Module X] Battery Pack 2 Operating Status             | Text     |
| [Module X] Battery Pack 3 Operating Status             | Text     |
| [Module X] Battery Pack 1 Voltage                      | V        |
| [Module X] Battery Pack 2 Voltage                      | V        |
| [Module X] Battery Pack 3 Voltage                      | V        |
| [Module X] Battery Pack 1 Charge/Discharge Power       | kW       |
| [Module X] Battery Pack 2 Charge/Discharge Power       | kW       |
| [Module X] Battery Pack 3 Charge/Discharge Power       | kW       |
| [Module X] Battery Pack 1 Maximum Temperature          | °C       |
| [Module X] Battery Pack 2 Maximum Temperature          | °C       |
| [Module X] Battery Pack 3 Maximum Temperature          | °C       |
| [Module X] Battery Pack 1 Minimum Temperature          | °C       |
| [Module X] Battery Pack 2 Minimum Temperature          | °C       |
| [Module X] Battery Pack 3 Minimum Temperature          | °C       |
| [Module X] Battery Pack 1 SOC                          | %        |
| [Module X] Battery Pack 2 SOC                          | %        |
| [Module X] Battery Pack 3 SOC                          | %        |
| [Module X] Battery Pack 1 Total Discharge Energy       | kWh      |
| [Module X] Battery Pack 2 Total Discharge Energy       | kWh      |
| [Module X] Battery Pack 3 Total Discharge Energy       | kWh      |
| [Module X] Battery Pack 1 Battery Health Check         | Text     |
| [Module X] Battery Pack 2 Battery Health Check         | Text     |
| [Module X] Battery Pack 3 Battery Health Check         | Text     |
| [Module X] Battery Pack 1 Heating Status               | Text     |
| [Module X] Battery Pack 2 Heating Status               | Text     |
| [Module X] Battery Pack 3 Heating Status               | Text     |

*X ranges from 1 - 4 depending on how many modules your battery has.
> [!NOTE] 
> Currently, this integration only supports battery modules 1 and 2.
> If your battery has 3 or 4 modules, please [open an issue](https://github.com/JortvanSchijndel/FusionSolarPlus/issues).

## Power Sensor
| Entity                       |    Unit     |
|------------------------------|:-----------:|
| Meter Status                 |    Text     |
| Positive Active Energy       |     kWh     |
| Negative Active Energy       |     kWh     |
| Reactive Power               |     Var     |
| Active Power                 |      W      |
| Power Factor                 | Ratio       |
| Phase A Active Power         |      W      |
| Phase B Active Power         |      W      |
| Phase C Active Power         |      W      |
| Phase A Voltage              |      V      |
| Phase B Voltage              |      V      |
| Phase C Voltage              |      V      |
| Phase A Current              |      A      |
| Phase B Current              |      A      |
| Phase C Current              |      A      |
| Grid Frequency               |     Hz      |

# Issues
If you encounter any problems while using the integration, please [open an issue](https://github.com/JortvanSchijndel/FusionSolarPlus/issues).
Be sure to include as much relevant information as possible, this helps with troubleshooting and speeds up the resolution process.

# Legal Notice
This integration for Home Assistant uses a custom modified version of [FusionSolarPy](https://github.com/jgriss/FusionSolarPy).

