"""Contract tests for the plant energy signals.

The plant sensors read the *daily* energy-balance endpoint (`timeDim: 2`), which is
why a family of keys carries lifetime-sounding names but today's numbers
(issue #132). The fix adds explicitly daily twins instead of renaming, so this
test pins the three properties that make that work: the twins exist, they are
opt-in, and they read the same API field as their legacy counterpart.

Parsed with `ast` rather than imported: importing the integration pulls in Home
Assistant, and the point here is the data, not the plumbing.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONST = ROOT / "custom_components/fusionsolarplus/devices/plant/const.py"
PLANT_API = ROOT / "custom_components/fusionsolarplus/api/devices/plant_api.py"

# daily twin key -> (legacy key it duplicates, API field it reads)
EXPECTED_TWINS = {
    "totalConsumptionEnergyToday": ("totalConsumptionEnergy", "totalUsePower"),
    "totalGridImportEnergyToday": ("totalGridImportEnergy", "totalBuyPower"),
    "totalFeedInEnergyToday": ("totalFeedInEnergy", "totalOnGridPower"),
    "totalSelfUseEnergyToday": ("totalSelfUseEnergy", "totalSelfUsePower"),
}


def _literal(node):
    """Best-effort literal evaluation for a signal dict or a string map."""
    if isinstance(node, ast.Dict):
        out = {}
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant):
                continue
            try:
                out[key.value] = ast.literal_eval(value)
            except ValueError:
                # e.g. SensorStateClass.TOTAL -> keep the attribute path
                out[key.value] = ast.unparse(value)
        return out
    return ast.literal_eval(node)


def _plant_signals():
    tree = ast.parse(CONST.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PLANT_SIGNALS" for t in node.targets
        ):
            return [_literal(elt) for elt in node.value.elts]
    raise AssertionError("PLANT_SIGNALS not found")


def _aliases():
    tree = ast.parse(PLANT_API.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ENERGY_FIELD_ALIASES"
            for t in node.targets
        ):
            return _literal(node.value)
    raise AssertionError("ENERGY_FIELD_ALIASES not found")


def test_daily_twins_are_defined_and_opt_in():
    signals = {signal["key"]: signal for signal in _plant_signals()}
    for key in EXPECTED_TWINS:
        assert key in signals, f"{key} missing from PLANT_SIGNALS"
        signal = signals[key]
        assert signal["name"].startswith("Daily "), signal["name"]
        assert signal["unit"] == "kWh"
        assert signal["state_class"].endswith("TOTAL"), signal["state_class"]
        assert signal["enabled_by_default"] is False, key


def test_daily_twins_read_the_same_field_as_their_legacy_counterpart():
    aliases = _aliases()
    signals = {signal["key"]: signal for signal in _plant_signals()}
    assert set(aliases) == set(EXPECTED_TWINS)
    for key, (_legacy, field) in EXPECTED_TWINS.items():
        assert aliases[key] == field, (key, aliases[key])
        assert key in signals


def test_legacy_keys_are_untouched():
    """The PR is additive: nothing existing may be renamed or re-classed."""
    signals = {signal["key"]: signal for signal in _plant_signals()}
    for key, (legacy, _field) in EXPECTED_TWINS.items():
        assert legacy in signals, f"{legacy} disappeared"
        assert signals[legacy]["state_class"].endswith("TOTAL_INCREASING")
        assert signals[legacy]["name"] != signals[key]["name"]
