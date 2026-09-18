"""Unit tests for request and response schema validation."""

import unittest
from pydantic import ValidationError
from app.models.schemas import (
    HourInput,
    BatteryInput,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    DirectiveInterpretationItem,
    HourlyPlanItem,
    HealthResponse,
    ErrorEnvelope,
)


def _make_valid_hours():
    return [
        {"hour": h, "demand_kwh": 50.0 + h, "solar_kwh": 10.0 + h, "tariff_bdt_per_kwh": 10.0}
        for h in range(24)
    ]


def _make_valid_battery():
    return {
        "capacity_kwh": 200.0,
        "initial_energy_kwh": 100.0,
        "minimum_energy_kwh": 40.0,
        "max_charge_kwh_per_hour": 50.0,
        "max_discharge_kwh_per_hour": 50.0,
    }


class TestSchemas(unittest.TestCase):
    """Test strict schema behavior and rejection rules."""

    def test_valid_request(self):
        req_dict = {
            "scenario_id": "TEST-01",
            "operator_notes": ["Panel inspection between 1 PM and 3 PM."],
            "hours": _make_valid_hours(),
            "battery": _make_valid_battery(),
        }
        req = OptimizeEnergyRequest(**req_dict)
        self.assertEqual(req.scenario_id, "TEST-01")
        self.assertEqual(len(req.hours), 24)
        self.assertEqual(len(req.operator_notes), 1)

    def test_hours_out_of_order_accepted(self):
        hours = _make_valid_hours()
        # Reverse hours
        hours_reversed = list(reversed(hours))
        req_dict = {
            "scenario_id": "TEST-REVERSED",
            "operator_notes": ["Note 1"],
            "hours": hours_reversed,
            "battery": _make_valid_battery(),
        }
        req = OptimizeEnergyRequest(**req_dict)
        self.assertEqual(len(req.hours), 24)

    def test_missing_or_duplicate_hour_rejected(self):
        # 23 hours instead of 24
        hours = _make_valid_hours()[:23]
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST",
                operator_notes=["Note 1"],
                hours=hours,
                battery=_make_valid_battery(),
            )

        # Duplicate hour 0
        hours_dup = _make_valid_hours()
        hours_dup[1]["hour"] = 0
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST",
                operator_notes=["Note 1"],
                hours=hours_dup,
                battery=_make_valid_battery(),
            )

    def test_hour_out_of_bounds(self):
        with self.assertRaises(ValidationError):
            HourInput(hour=24, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=10.0)
        with self.assertRaises(ValidationError):
            HourInput(hour=-1, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=10.0)

    def test_booleans_and_non_finite_rejected(self):
        # Boolean used for demand_kwh
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=True, solar_kwh=5.0, tariff_bdt_per_kwh=10.0)  # type: ignore

        # NaN / Infinity
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=float("nan"), solar_kwh=5.0, tariff_bdt_per_kwh=10.0)
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=float("inf"), solar_kwh=5.0, tariff_bdt_per_kwh=10.0)

    def test_negative_values_rejected(self):
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=-5.0, solar_kwh=5.0, tariff_bdt_per_kwh=10.0)
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=10.0, solar_kwh=-1.0, tariff_bdt_per_kwh=10.0)
        with self.assertRaises(ValidationError):
            HourInput(hour=0, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=-2.0)

    def test_operator_notes_length_and_whitespace(self):
        # 0 notes
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST",
                operator_notes=[],
                hours=_make_valid_hours(),
                battery=_make_valid_battery(),
            )
        # 4 notes (max is 3)
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST",
                operator_notes=["n1", "n2", "n3", "n4"],
                hours=_make_valid_hours(),
                battery=_make_valid_battery(),
            )
        # Empty / whitespace note
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST",
                operator_notes=["   "],
                hours=_make_valid_hours(),
                battery=_make_valid_battery(),
            )

    def test_battery_inequality_bounds(self):
        # initial < minimum
        b1 = _make_valid_battery()
        b1["initial_energy_kwh"] = 20.0
        b1["minimum_energy_kwh"] = 50.0
        with self.assertRaises(ValidationError):
            BatteryInput(**b1)

        # initial > capacity
        b2 = _make_valid_battery()
        b2["initial_energy_kwh"] = 250.0
        b2["capacity_kwh"] = 200.0
        with self.assertRaises(ValidationError):
            BatteryInput(**b2)

        # minimum > capacity
        b3 = _make_valid_battery()
        b3["minimum_energy_kwh"] = 250.0
        b3["capacity_kwh"] = 200.0
        with self.assertRaises(ValidationError):
            BatteryInput(**b3)

        # negative capacity
        b4 = _make_valid_battery()
        b4["capacity_kwh"] = -10.0
        with self.assertRaises(ValidationError):
            BatteryInput(**b4)

    def test_extra_fields_forbidden(self):
        # Top-level extra field
        req_dict = {
            "scenario_id": "TEST-01",
            "operator_notes": ["Note 1"],
            "hours": _make_valid_hours(),
            "battery": _make_valid_battery(),
            "unexpected_field": "disallowed",
        }
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(**req_dict)

        # Extra field in hour item
        hours = _make_valid_hours()
        hours[0]["extra_hour_field"] = 123
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST-02",
                operator_notes=["Note 1"],
                hours=hours,
                battery=_make_valid_battery(),
            )

        # Extra field in battery
        battery = _make_valid_battery()
        battery["extra_battery_field"] = "bad"
        with self.assertRaises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="TEST-03",
                operator_notes=["Note 1"],
                hours=_make_valid_hours(),
                battery=battery,
            )

    def test_exact_scenario_id_echo(self):
        # Must preserve whitespace verbatim and not strip
        raw_id = "  SCENARIO_WITH_SPACES  "
        req_dict = {
            "scenario_id": raw_id,
            "operator_notes": ["Note 1"],
            "hours": _make_valid_hours(),
            "battery": _make_valid_battery(),
        }
        req = OptimizeEnergyRequest(**req_dict)
        self.assertEqual(req.scenario_id, raw_id)


if __name__ == "__main__":
    unittest.main()
