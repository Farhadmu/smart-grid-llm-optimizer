"""Unit tests for the independent chronological replay validator."""

import unittest
from app.models.schemas import HourInput, BatteryInput, HourlyPlanItem, DirectiveInterpretationItem
from app.optimizer.compiler import compile_scenario_and_directives
from app.replay.validator import replay_and_recalculate_plan, ReplayValidationError


def _make_base_plan():
    # Base 24-hour plan: demand 100, solar 50, grid 50, idle battery 100
    return [
        HourlyPlanItem(
            hour=h,
            grid_kwh=50.0,
            solar_used_kwh=50.0,
            battery_action="idle",
            battery_kwh=0.0,
            battery_energy_after_kwh=100.0,
        )
        for h in range(24)
    ]


def _make_base_compiled():
    hours = [
        HourInput(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0)
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=20.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    return compile_scenario_and_directives("TEST", hours, battery, [])


class TestReplayValidator(unittest.TestCase):
    """Verify that independent replay catches every energy and directive violation."""

    def test_valid_plan_passes(self):
        plan = _make_base_plan()
        compiled = _make_base_compiled()
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)
        self.assertAlmostEqual(grid, 1200.0)
        self.assertAlmostEqual(cost, 12000.0)
        self.assertAlmostEqual(peak, 50.0)

    def test_missing_or_duplicate_hour_fails(self):
        compiled = _make_base_compiled()
        # 23 items
        plan_short = _make_base_plan()[:23]
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan_short, compiled)

        # Duplicate hour
        plan_dup = _make_base_plan()
        plan_dup[1].hour = 0
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan_dup, compiled)

    def test_negative_value_fails(self):
        plan = _make_base_plan()
        plan[5].grid_kwh = -1.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_action_magnitude_inconsistency_fails(self):
        compiled = _make_base_compiled()

        # idle with battery_kwh > 0
        plan1 = _make_base_plan()
        plan1[0].battery_action = "idle"
        plan1[0].battery_kwh = 10.0
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan1, compiled)

        # charge with battery_kwh == 0
        plan2 = _make_base_plan()
        plan2[0].battery_action = "charge"
        plan2[0].battery_kwh = 0.0
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan2, compiled)

    def test_battery_transition_mismatch_fails(self):
        plan = _make_base_plan()
        # Says charge 20, but energy after is still 100 instead of 120
        plan[0].battery_action = "charge"
        plan[0].battery_kwh = 20.0
        plan[0].grid_kwh = 70.0  # balance: 70 + 50 = 100 + 20
        plan[0].battery_energy_after_kwh = 100.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_charge_rate_limit_fails(self):
        plan = _make_base_plan()
        plan[0].battery_action = "charge"
        plan[0].battery_kwh = 80.0  # Max charge rate is 50.0
        plan[0].battery_energy_after_kwh = 180.0
        plan[0].grid_kwh = 130.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_discharge_rate_limit_fails(self):
        plan = _make_base_plan()
        plan[0].battery_action = "discharge"
        plan[0].battery_kwh = 80.0  # Max discharge rate is 50.0
        plan[0].battery_energy_after_kwh = 20.0
        plan[0].grid_kwh = 0.0  # balance: 0 + 50 + 80 = 100 + 0 -> 130 != 100
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_capacity_exceeded_fails(self):
        plan = _make_base_plan()
        plan[0].battery_energy_after_kwh = 250.0  # Capacity is 200.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_minimum_reserve_violated_fails(self):
        plan = _make_base_plan()
        plan[0].battery_energy_after_kwh = 10.0  # Min is 20.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_no_charge_directive_violation_fails(self):
        plan = _make_base_plan()
        # Hour 14 charges 10 kWh
        plan[14].battery_action = "charge"
        plan[14].battery_kwh = 10.0
        plan[14].battery_energy_after_kwh = 110.0
        plan[14].grid_kwh = 60.0
        # Subsequent hour discharges to maintain neutrality
        plan[15].battery_action = "discharge"
        plan[15].battery_kwh = 10.0
        plan[15].battery_energy_after_kwh = 100.0
        plan[15].grid_kwh = 40.0

        # But directive forbids charge in hour 14
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": [14]},
                explanation="no charge at 14",
            )
        ]
        compiled = compile_scenario_and_directives("TEST", [
            HourInput(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0)
            for h in range(24)
        ], BatteryInput(
            capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0,
        ), directives)

        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_solar_used_exceeds_effective_fails(self):
        plan = _make_base_plan()
        plan[5].solar_used_kwh = 80.0  # Base solar is 50.0
        plan[5].grid_kwh = 20.0        # sum is still 100
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_grid_cap_exceeded_fails(self):
        plan = _make_base_plan()  # grid is 50.0
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": [10], "max_grid_kwh": 40.0},
                explanation="cap at 40",
            )
        ]
        compiled = compile_scenario_and_directives("TEST", [
            HourInput(hour=h, demand_kwh=100.0, solar_kwh=50.0, tariff_bdt_per_kwh=10.0)
            for h in range(24)
        ], BatteryInput(
            capacity_kwh=200.0, initial_energy_kwh=100.0, minimum_energy_kwh=20.0,
            max_charge_kwh_per_hour=50.0, max_discharge_kwh_per_hour=50.0,
        ), directives)

        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_hourly_energy_balance_violation_fails(self):
        plan = _make_base_plan()
        plan[3].grid_kwh = 40.0  # 40 + 50 = 90 != 100 demand
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)

    def test_end_of_day_neutrality_fails(self):
        plan = _make_base_plan()
        # Battery ends at 110 instead of 100
        plan[23].battery_energy_after_kwh = 110.0
        compiled = _make_base_compiled()
        with self.assertRaises(ReplayValidationError):
            replay_and_recalculate_plan(plan, compiled)


if __name__ == "__main__":
    unittest.main()
