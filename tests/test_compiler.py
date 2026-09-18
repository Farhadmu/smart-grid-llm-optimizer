"""Unit tests for directive compilation and conservative overlap policy."""

import unittest
import numpy as np
from app.models.schemas import (
    HourInput,
    BatteryInput,
    DirectiveInterpretationItem,
)
from app.optimizer.compiler import compile_scenario_and_directives


def _base_hours():
    return [
        HourInput(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]


def _base_battery():
    return BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=20.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )


class TestCompiler(unittest.TestCase):
    """Verify conservative intersection combination policy."""

    def test_overlapping_solar_reductions_take_minimum_factor(self):
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="solar_reduction",
                structured_adjustment={"hours": [12, 13, 14], "factor": 0.5},
                explanation="1st solar reduction",
            ),
            DirectiveInterpretationItem(
                note_index=1,
                applies=True,
                directive_type="solar_reduction",
                structured_adjustment={"hours": [13, 14, 15], "factor": 0.2},
                explanation="2nd solar reduction",
            ),
        ]
        compiled = compile_scenario_and_directives("TEST", _base_hours(), _base_battery(), directives)

        # Base solar is 50.0
        # Hour 12: only 1st applies (0.5) -> 25.0
        # Hour 13 & 14: both apply -> min(0.5, 0.2) = 0.2 -> 10.0
        # Hour 15: only 2nd applies (0.2) -> 10.0
        # Hour 11: unaffected -> 50.0
        self.assertAlmostEqual(compiled.effective_solar[11], 50.0)
        self.assertAlmostEqual(compiled.effective_solar[12], 25.0)
        self.assertAlmostEqual(compiled.effective_solar[13], 10.0)
        self.assertAlmostEqual(compiled.effective_solar[14], 10.0)
        self.assertAlmostEqual(compiled.effective_solar[15], 10.0)

    def test_overlapping_battery_reserves_take_maximum(self):
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="minimum_battery_reserve",
                structured_adjustment={"hours": [18, 19], "minimum_energy_kwh": 80.0},
                explanation="1st reserve",
            ),
            DirectiveInterpretationItem(
                note_index=1,
                applies=True,
                directive_type="minimum_battery_reserve",
                structured_adjustment={"hours": [19, 20], "minimum_energy_kwh": 120.0},
                explanation="2nd reserve",
            ),
        ]
        compiled = compile_scenario_and_directives("TEST", _base_hours(), _base_battery(), directives)

        # Base min is 20.0
        # Hour 18: 80.0
        # Hour 19: max(80.0, 120.0) = 120.0
        # Hour 20: 120.0
        # Hour 21: base 20.0
        self.assertAlmostEqual(compiled.active_min_energy[18], 80.0)
        self.assertAlmostEqual(compiled.active_min_energy[19], 120.0)
        self.assertAlmostEqual(compiled.active_min_energy[20], 120.0)
        self.assertAlmostEqual(compiled.active_min_energy[21], 20.0)

    def test_overlapping_grid_caps_take_minimum(self):
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": [18, 19], "max_grid_kwh": 150.0},
                explanation="1st cap",
            ),
            DirectiveInterpretationItem(
                note_index=1,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": [19, 20], "max_grid_kwh": 120.0},
                explanation="2nd cap",
            ),
        ]
        compiled = compile_scenario_and_directives("TEST", _base_hours(), _base_battery(), directives)

        self.assertAlmostEqual(compiled.grid_cap[18], 150.0)
        self.assertAlmostEqual(compiled.grid_cap[19], 120.0)
        self.assertAlmostEqual(compiled.grid_cap[20], 120.0)
        self.assertTrue(np.isinf(compiled.grid_cap[21]))

    def test_no_charge_and_no_discharge_windows(self):
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": [14, 15]},
                explanation="no charge",
            ),
            DirectiveInterpretationItem(
                note_index=1,
                applies=True,
                directive_type="no_discharge_window",
                structured_adjustment={"hours": [15, 16]},
                explanation="no discharge",
            ),
        ]
        compiled = compile_scenario_and_directives("TEST", _base_hours(), _base_battery(), directives)

        self.assertFalse(compiled.charge_allowed[14])
        self.assertTrue(compiled.discharge_allowed[14])

        # Hour 15: both forbidden
        self.assertFalse(compiled.charge_allowed[15])
        self.assertFalse(compiled.discharge_allowed[15])

        self.assertTrue(compiled.charge_allowed[16])
        self.assertFalse(compiled.discharge_allowed[16])


if __name__ == "__main__":
    unittest.main()
