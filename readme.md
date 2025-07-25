
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

___
> [!NOTE] 
> For some development (eg. batteries, optimizers & car chargers) I will need access to an account which has access to (one of) these devices. 
> If you are willing to help by granting me access to your account, please [open an issue](https://github.com/JortvanSchijndel/FusionSolarPlus/issues).

# FusionSolarPlus
This integration brings full FusionSolar support to Home Assistant, with entities for plants, inverters, and more. It authenticates using your FusionSolar username and password. No northbound API, OpenAPI, or kiosk URL required. I originally built it as a custom Python script that sent data via MQTT, but realizing others might want a Home Assistant integration with full entity support, I ported it with AI assistance into a proper integration for easier use.

## Setup
Click the button below and download the FusionSolarPlus integration.

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=JortvanSchijndel&repository=FusionSolarPlus&category=Integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

Once installed:

1. Restart Home Assistant and head over to **Settings » Devices & Services.**  
2. Click on **"Add Integration."**  
3. Search for **"FusionSolarPlus."**  
4. Enter your FusionSolar username, password and subdomain. (For a list of available subdomains click [here](https://support.huawei.com/enterprise/en/doc/EDOC1100165054/dbeb5df3/domain-name-list-of-management-systems). eg. 'region01eu5)  
5. Select the device type you want to add, then choose the specific device.

# Energy Dashboard

FusionSolarPlus is fully compatible with the integrated Home Assistant energy dashboard. When configuring the energy dashboard you need to provide the following settings:

|                          | Energy dashboard setting         | Device Type  | Entity                                                              |
|--------------------------|----------------------------------|:------------:|---------------------------------------------------------------------|
| **Electricity Grid**     | Grid Consumption                 | Power Sensor | Negative Active Energy                                              |
|                          | Return to Grid                   | Power Sensor | Positive Active Energy                                              |
| **Home Battery Storage** | Energy going in to the battery   |   Battery    | Energy Charged Today                                                |
|                          | Energy coming out of the battery |   Battery    | Energy Discharged Today                                             |
| **Solar Panels**         | Solar Production                 |    Plant     | Total Energy **or** Total Energy Produced for each of the inverters |
# Entities

<details>

<summary>Click here to see the list of entities</summary>

### Inverter & Plant
<table>
   <tr>
      <td width="50" align="center"><b>#</b></td>
      <td width="400"><b>Inverter Entity</b></td>
      <td width="100" align="center"><b>Unit</b></td>
      <td width="75"></td>
      <td width="400"><b>Plant Entity</b></td>
      <td width="100" align="center"><b>Unit</b></td>
   </tr>
   <tr>
      <td align="center">1</td>
      <td>Current Active Power</td>
      <td align="center">kW</td>
      <td></td>
      <td>Current Power</td>
      <td align="center">kW</td>
   </tr>
   <tr>
      <td align="center">2</td>
      <td>Daily Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td>Today Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">3</td>
      <td>Grid Frequency</td>
      <td align="center">Hz</td>
      <td></td>
      <td>Monthly Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">4</td>
      <td>Insulation Resistance</td>
      <td align="center">MΩ</td>
      <td></td>
      <td>Yearly Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">5</td>
      <td>Last Shutdown Time</td>
      <td align="center">Datetime</td>
      <td></td>
      <td>Total Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">6</td>
      <td>Last Startup Time</td>
      <td align="center">Datetime</td>
      <td></td>
      <td>Today Income</td>
      <td align="center"><a href="https://en.wikipedia.org/wiki/ISO_4217#Active_codes">ISO 4217</a></td>
   </tr>
   <tr>
      <td align="center">7</td>
      <td>Output Mode</td>
      <td align="center">Text</td>
      <td></td>
      <td>Self Used Energy Today**</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">8</td>
      <td>Phase A Current</td>
      <td align="center">A</td>
      <td></td>
      <td>Consumption Today**</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">9</td>
      <td>Phase A Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">10</td>
      <td>Phase B Current</td>
      <td align="center">A</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">11</td>
      <td>Phase B Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">12</td>
      <td>Phase C Current</td>
      <td align="center">A</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">13</td>
      <td>Phase C Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">14</td>
      <td>Power Factor</td>
      <td align="center">Ratio</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">15</td>
      <td>Rated Power</td>
      <td align="center">kW</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">16</td>
      <td>Reactive Power</td>
      <td align="center">kvar</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">17</td>
      <td>Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">18</td>
      <td>Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">19</td>
      <td>Total Energy Produced</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">20</td>
      <td>[PV X] Input Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">21</td>
      <td>[PV X] Input Current</td>
      <td align="center">A</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">22</td>
      <td>[PV X] Input Power</td>
      <td align="center">W</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
</table>

*X ranges from 1 - 20 depending on how many PV Strings your inverter has connected.

**These entities only show up if you have a power meter connected.

### Battery & Optimizer

<table>
   <tr>
      <td width="50" align="center"><b>#</b></td>
      <td width="400"><b>Battery Entity</b></td>
      <td width="100" align="center"><b>Unit</b></td>
      <td width="75"></td>
      <td width="400"><b>Optimizer Entity</b></td>
      <td width="100" align="center"><b>Unit</b></td>
   </tr>
   <tr>
      <td align="center">1</td>
      <td>Operating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td>Output Power</td>
      <td align="center">W</td>
   </tr>
   <tr>
      <td align="center">2</td>
      <td>Charge/Discharge Mode</td>
      <td align="center">Text</td>
      <td></td>
      <td>Total Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">3</td>
      <td>Rated Capacity</td>
      <td align="center">kWh</td>
      <td></td>
      <td>Input Voltage</td>
      <td align="center">V</td>
   </tr>
   <tr>
      <td align="center">4</td>
      <td>Backup Time</td>
      <td align="center">min</td>
      <td></td>
      <td>Running Status</td>
      <td align="center">Text</td>
   </tr>
   <tr>
      <td align="center">5</td>
      <td>Energy Charged Today</td>
      <td align="center">kWh</td>
      <td></td>
      <td>Temperature</td>
      <td align="center">°C</td>
   </tr>
   <tr>
      <td align="center">6</td>
      <td>Energy Discharged Today</td>
      <td align="center">kWh</td>
      <td></td>
      <td>Serial Number (SN)</td>
      <td align="center">Text</td>
   </tr>
   <tr>
      <td align="center">7</td>
      <td>Charge/Discharge Power</td>
      <td align="center">kW</td>
      <td></td>
      <td>Optimizer Number</td>
      <td align="center">Text</td>
   </tr>
   <tr>
      <td align="center">8</td>
      <td>Bus Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td>Output Voltage</td>
      <td align="center">V</td>
   </tr>
   <tr>
      <td align="center">9</td>
      <td>State of Charge</td>
      <td align="center">%</td>
      <td></td>
      <td>Input Current</td>
      <td align="center">A</td>
   </tr>
   <!-- Module-specific rows without counter on Optimizer side -->
   <tr>
      <td align="center">10</td>
      <td>[Module X] No.</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">11</td>
      <td>[Module X] Working Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">12</td>
      <td>[Module X] SN</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">13</td>
      <td>[Module X] Software Version</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">14</td>
      <td>[Module X] SOC</td>
      <td align="center">%</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">15</td>
      <td>[Module X] Charge and Discharge Power</td>
      <td align="center">kW</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">16</td>
      <td>[Module X] Internal Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">17</td>
      <td>[Module X] Daily Charge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">18</td>
      <td>[Module X] Daily Discharge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">19</td>
      <td>[Module X] Total Discharge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">20</td>
      <td>[Module X] Bus Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">21</td>
      <td>[Module X] Bus Current</td>
      <td align="center">A</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">22</td>
      <td>[Module X] FE Connection</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">23</td>
      <td>[Module X] Total Charge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">24</td>
      <td>[Module X] Battery Pack 1 No.</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">25</td>
      <td>[Module X] Battery Pack 2 No.</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">26</td>
      <td>[Module X] Battery Pack 3 No.</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">27</td>
      <td>[Module X] Battery Pack 1 Firmware Version</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">28</td>
      <td>[Module X] Battery Pack 2 Firmware Version</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">29</td>
      <td>[Module X] Battery Pack 3 Firmware Version</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">30</td>
      <td>[Module X] Battery Pack 1 SN</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">31</td>
      <td>[Module X] Battery Pack 2 SN</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">32</td>
      <td>[Module X] Battery Pack 3 SN</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">33</td>
      <td>[Module X] Battery Pack 1 Operating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">34</td>
      <td>[Module X] Battery Pack 2 Operating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">35</td>
      <td>[Module X] Battery Pack 3 Operating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">36</td>
      <td>[Module X] Battery Pack 1 Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">37</td>
      <td>[Module X] Battery Pack 2 Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">38</td>
      <td>[Module X] Battery Pack 3 Voltage</td>
      <td align="center">V</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">39</td>
      <td>[Module X] Battery Pack 1 Charge/Discharge Power</td>
      <td align="center">kW</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">40</td>
      <td>[Module X] Battery Pack 2 Charge/Discharge Power</td>
      <td align="center">kW</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">41</td>
      <td>[Module X] Battery Pack 3 Charge/Discharge Power</td>
      <td align="center">kW</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">42</td>
      <td>[Module X] Battery Pack 1 Maximum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">43</td>
      <td>[Module X] Battery Pack 2 Maximum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">44</td>
      <td>[Module X] Battery Pack 3 Maximum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">45</td>
      <td>[Module X] Battery Pack 1 Minimum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">46</td>
      <td>[Module X] Battery Pack 2 Minimum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">47</td>
      <td>[Module X] Battery Pack 3 Minimum Temperature</td>
      <td align="center">°C</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">48</td>
      <td>[Module X] Battery Pack 1 SOC</td>
      <td align="center">%</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">49</td>
      <td>[Module X] Battery Pack 2 SOC</td>
      <td align="center">%</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">50</td>
      <td>[Module X] Battery Pack 3 SOC</td>
      <td align="center">%</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">51</td>
      <td>[Module X] Battery Pack 1 Total Discharge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">52</td>
      <td>[Module X] Battery Pack 2 Total Discharge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">53</td>
      <td>[Module X] Battery Pack 3 Total Discharge Energy</td>
      <td align="center">kWh</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">54</td>
      <td>[Module X] Battery Pack 1 Battery Health Check</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">55</td>
      <td>[Module X] Battery Pack 2 Battery Health Check</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">56</td>
      <td>[Module X] Battery Pack 3 Battery Health Check</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">57</td>
      <td>[Module X] Battery Pack 1 Heating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">58</td>
      <td>[Module X] Battery Pack 2 Heating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
   <tr>
      <td align="center">59</td>
      <td>[Module X] Battery Pack 3 Heating Status</td>
      <td align="center">Text</td>
      <td></td>
      <td></td>
      <td></td>
   </tr>
</table>
*The optimizer entities can be found under the Diagnostic section for Inverter devices. The optimizer entities are automatically created if your inverter has optimizers connected.

**X ranges from 1 - 4 depending on how many modules your battery has.

**⚠️ Note:** Currently, this integration only supports battery modules 1 and 2. If your battery has 3 or 4 modules, please [open an issue](https://github.com/JortvanSchijndel/FusionSolarPlus/issues).

### Power Sensor

<table>
   <tr>
      <td width="50" align="center"><b>#</b></td>
      <td width="400"><b>Power Sensor Entity</b></td>
      <td width="100" align="center"><b>Unit</b></td>
   </tr>
   <tr>
      <td align="center">1</td>
      <td>Meter Status</td>
      <td align="center">Text</td>
   </tr>
   <tr>
      <td align="center">2</td>
      <td>Positive Active Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">3</td>
      <td>Negative Active Energy</td>
      <td align="center">kWh</td>
   </tr>
   <tr>
      <td align="center">4</td>
      <td>Reactive Power</td>
      <td align="center">Var</td>
   </tr>
   <tr>
      <td align="center">5</td>
      <td>Active Power</td>
      <td align="center">W</td>
   </tr>
   <tr>
      <td align="center">6</td>
      <td>Power Factor</td>
      <td align="center">Ratio</td>
   </tr>
   <tr>
      <td align="center">7</td>
      <td>Phase A Active Power</td>
      <td align="center">W</td>
   </tr>
   <tr>
      <td align="center">8</td>
      <td>Phase B Active Power</td>
      <td align="center">W</td>
   </tr>
   <tr>
      <td align="center">9</td>
      <td>Phase C Active Power</td>
      <td align="center">W</td>
   </tr>
   <tr>
      <td align="center">10</td>
      <td>Phase A Voltage</td>
      <td align="center">V</td>
   </tr>
   <tr>
      <td align="center">11</td>
      <td>Phase B Voltage</td>
      <td align="center">V</td>
   </tr>
   <tr>
      <td align="center">12</td>
      <td>Phase C Voltage</td>
      <td align="center">V</td>
   </tr>
   <tr>
      <td align="center">13</td>
      <td>Phase A Current</td>
      <td align="center">A</td>
   </tr>
   <tr>
      <td align="center">14</td>
      <td>Phase B Current</td>
      <td align="center">A</td>
   </tr>
   <tr>
      <td align="center">15</td>
      <td>Phase C Current</td>
      <td align="center">A</td>
   </tr>
   <tr>
      <td align="center">16</td>
      <td>Grid Frequency</td>
      <td align="center">Hz</td>
   </tr>
</table>
</details>

# Issues
If you encounter any problems while using the integration, please [open an issue](https://github.com/JortvanSchijndel/FusionSolarPlus/issues).
Be sure to include as much relevant information as possible, this helps with troubleshooting and speeds up the resolution process.

# Legal Notice
This integration for Home Assistant uses a custom modified version of [FusionSolarPy](https://github.com/jgriss/FusionSolarPy).

