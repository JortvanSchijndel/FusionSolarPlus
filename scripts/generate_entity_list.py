import os
import sys
import importlib.util
import types


# Mock homeassistant structure to avoid import errors
def mock_homeassistant():
    if "homeassistant" not in sys.modules:
        sys.modules["homeassistant"] = types.ModuleType("homeassistant")
    if "homeassistant.components" not in sys.modules:
        sys.modules["homeassistant.components"] = types.ModuleType(
            "homeassistant.components"
        )

    # Mock sensor module
    sensor_module = types.ModuleType("homeassistant.components.sensor")

    class MockSensorDeviceClass:
        ENUM = "enum"
        POWER_FACTOR = "power_factor"
        ENERGY = "energy"
        POWER = "power"
        REACTIVE_POWER = "reactive_power"
        FREQUENCY = "frequency"
        CURRENT = "current"
        VOLTAGE = "voltage"
        TEMPERATURE = "temperature"
        BATTERY = "battery"
        DURATION = "duration"
        MONETARY = "monetary"
        SIGNAL_STRENGTH = "signal_strength"

    class MockSensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"
        TOTAL = "total"

    sensor_module.SensorDeviceClass = MockSensorDeviceClass
    sensor_module.SensorStateClass = MockSensorStateClass

    sys.modules["homeassistant.components.sensor"] = sensor_module


mock_homeassistant()


def load_module_from_path(path, name):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"Error loading module {name} from {path}: {e}")
        return None


def generate_table(title, signals, override_count=None, note=None):
    if not signals:
        return ""

    # Add a header for the table if it's a specific array
    output = f"\n<p><b>{title}</b></p>\n"
    output += '<table>\n   <tr>\n      <td align="center"><b>#</b></td>\n      <td><b>Entity Display Name</b></td>\n      <td align="center"><b>Unit</b></td>\n   </tr>\n'

    count = 0
    for i, signal in enumerate(signals):
        if override_count and count >= override_count:
            break

        name = signal.get("custom_name", signal.get("name", "Unknown"))
        unit = signal.get("unit", "")
        if unit is None:
            unit = ""

        output += f'   <tr>\n      <td align="center">{i + 1}</td>\n      <td>{name}</td>\n      <td align="center">{unit}</td>\n   </tr>\n'
        count += 1

    output += "</table>\n"
    if note:
        output += f"<p><i>{note}</i></p>\n"
    return output


def generate_entity_list():
    print("Starting entity list generation...")

    # Get the project root directory
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"Project root: {base_path}")

    devices = [
        {
            "name": "Inverter",
            "const_path": "custom_components/fusionsolarplus/devices/inverter/const.py",
            "arrays": [
                {"name": "Inverter Signals", "var": "INVERTER_SIGNALS"},
                {
                    "name": "PV Signals",
                    "var": "PV_SIGNALS",
                    "override_count": 3,
                    "note": "* [PV 1] can be [PV 1] to [PV 20] depending on your device.",
                },
                {"name": "Optimizer Metrics", "var": "OPTIMIZER_METRICS"},
            ],
        },
        {
            "name": "Battery",
            "const_path": "custom_components/fusionsolarplus/devices/battery/const.py",
            "arrays": [
                {"name": "Battery Status Signals", "var": "BATTERY_STATUS_SIGNALS"},
                {
                    "name": "Battery Module Signals",
                    "var": "BATTERY_MODULE_SIGNALS_1",
                    "note": "* [Module 1] can be [Module 1] to [Module 4] depending on your device.",
                },
            ],
        },
        {
            "name": "Power Sensor",
            "const_path": "custom_components/fusionsolarplus/devices/powersensor/const.py",
            "arrays": [
                {"name": "Power Sensor Signals", "var": "POWER_SENSOR_SIGNALS"},
                {"name": "Emma A02 Signals", "var": "EMMA_A02_SIGNALS"},
                {"name": "DTSU666-FE Signals", "var": "DTSU666_FE_SIGNALS"},
            ],
        },
        {
            "name": "Charger",
            "const_path": "custom_components/fusionsolarplus/devices/charger/const.py",
            "arrays": [
                {"name": "Charging Pile Signals", "var": "CHARGING_PILE_SIGNALS"},
                {"name": "Charger Device Signals", "var": "CHARGER_DEVICE_SIGNALS"},
            ],
        },
        {
            "name": "Plant",
            "const_path": "custom_components/fusionsolarplus/devices/plant/const.py",
            "arrays": [{"name": "Plant Signals", "var": "PLANT_SIGNALS"}],
        },
        {
            "name": "BackupBox",
            "const_path": "custom_components/fusionsolarplus/devices/backupbox/const.py",
            "arrays": [{"name": "BackupBox Signals", "var": "BACKUPBOX_SIGNALS"}],
        },
        {
            "name": "EMMA",
            "const_path": "custom_components/fusionsolarplus/devices/emma/const.py",
            "arrays": [{"name": "EMMA Signals", "var": "EMMA_SIGNALS"}],
        },
    ]

    output = "# Entities\n\n\n<details>\n<summary>Click here to see the list of entities </summary>\n\n"

    for device in devices:
        full_path = os.path.join(base_path, device["const_path"])
        if not os.path.exists(full_path):
            print(f"Warning: File not found: {full_path}")
            continue

        module_name = f"const_{device['name'].lower()}"
        module = load_module_from_path(full_path, module_name)

        if not module:
            continue

        # Check if any arrays exist for this device
        has_content = False
        for array_info in device["arrays"]:
            if hasattr(module, array_info["var"]):
                has_content = True
                break

        if has_content:
            print(f"Processing {device['name']}...")
            output += (
                f"<details>\n<summary><b><ins>{device['name']}</ins></b></summary>\n"
            )

            for array_info in device["arrays"]:
                if hasattr(module, array_info["var"]):
                    signals = getattr(module, array_info["var"])
                    override_count = array_info.get("override_count")
                    note = array_info.get("note")
                    output += generate_table(
                        array_info["name"], signals, override_count, note
                    )

            output += "</details>\n\n"

    output += "</details>\n"

    readme_path = os.path.join(base_path, "readme.md")
    if not os.path.exists(readme_path):
        print(f"Error: readme.md not found at {readme_path}")
        return

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace the Entities section
    start_marker = "# Entities"
    end_marker = "# Issues"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        new_content = content[:start_idx] + output + "\n" + content[end_idx:]
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("readme.md updated successfully")
    else:
        print(
            f"Could not find markers in readme.md. Start: {start_idx}, End: {end_idx}"
        )
        print(f"Start marker: '{start_marker}'")
        print(f"End marker: '{end_marker}'")


if __name__ == "__main__":
    generate_entity_list()
