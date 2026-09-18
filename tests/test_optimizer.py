"""Unit tests for the linear programming optimizer."""

import unittest
import numpy as np
from app.models.schemas import HourInput, BatteryInput, DirectiveInterpretationItem
from app.optimizer.compiler import compile_scenario_and_directives
from app.optimizer.solver import solve_energy_optimization, map_solution_to_hourly_plan, SolverError
from app.replay.validator import replay_and_recalculate_plan


def _make_scenario(demand_val=100.0, solar_val=50.0, tariff_pattern="variable"):
    hours = []
    for h in range(24):
        if tariff_pattern == "variable":
            tariff = 5.0 if h < 6 or h >= 22 else 15.0  # off-peak vs peak
        elif tariff_pattern == "zero":
            tariff = 0.0
        elif tariff_pattern == "equal":
            tariff = 10.0
        hours.append(HourInput(hour=h, demand_kwh=demand_val, solar_kwh=solar_val, tariff_bdt_per_kwh=tariff))
    return hours


def _make_battery(capacity=200.0, initial=100.0, minimum=20.0, max_charge=50.0, max_discharge=50.0):
    return BatteryInput(
        capacity_kwh=capacity,
        initial_energy_kwh=initial,
        minimum_energy_kwh=minimum,
        max_charge_kwh_per_hour=max_charge,
        max_discharge_kwh_per_hour=max_discharge,
    )


class TestOptimizer(unittest.TestCase):
    """Verify linear optimizer correctness and physical constraints."""

    def test_basic_optimization_and_neutrality(self):
        hours = _make_scenario()
        battery = _make_battery()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        self.assertTrue(solution.success)
        plan = map_solution_to_hourly_plan(solution)
        self.assertEqual(len(plan), 24)

        # Verify replay passes
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)
        self.assertAlmostEqual(plan[23].battery_energy_after_kwh, 100.0, places=2)

    def test_battery_arbitrage_behavior(self):
        """Battery should charge during off-peak and discharge during peak."""
        hours = _make_scenario(demand_val=80.0, solar_val=0.0, tariff_pattern="variable")
        battery = _make_battery(capacity=200.0, initial=100.0, minimum=20.0, max_charge=50.0, max_discharge=50.0)
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)

        # Off-peak hours (0..5, 22..23) vs peak (6..21)
        # Verify that battery discharges during peak
        discharged_in_peak = any(item.battery_action == "discharge" for item in plan[6:22])
        self.assertTrue(discharged_in_peak)

    def test_zero_demand_and_zero_solar(self):
        hours = _make_scenario(demand_val=0.0, solar_val=0.0)
        battery = _make_battery()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)
        self.assertAlmostEqual(cost, 0.0, places=2)
        self.assertAlmostEqual(grid, 0.0, places=2)

    def test_solar_surplus_and_curtailment_no_grid_export(self):
        """Solar generation exceeds demand; excess must be curtailed without negative grid import."""
        hours = _make_scenario(demand_val=20.0, solar_val=200.0)
        battery = _make_battery()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)

        # Grid must be 0 for all hours (cannot export)
        for item in plan:
            self.assertGreaterEqual(item.grid_kwh, 0.0)
            self.assertLessEqual(item.solar_used_kwh, 200.0)

    def test_battery_at_capacity_boundary(self):
        battery = _make_battery(capacity=200.0, initial=200.0, minimum=20.0)
        hours = _make_scenario()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)
        self.assertAlmostEqual(plan[23].battery_energy_after_kwh, 200.0, places=2)

    def test_battery_at_minimum_boundary(self):
        battery = _make_battery(capacity=200.0, initial=20.0, minimum=20.0)
        hours = _make_scenario()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        grid, cost, peak = replay_and_recalculate_plan(plan, compiled)
        self.assertAlmostEqual(plan[23].battery_energy_after_kwh, 20.0, places=2)

    def test_zero_battery_rates(self):
        battery = _make_battery(max_charge=0.0, max_discharge=0.0)
        hours = _make_scenario()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        for item in plan:
            self.assertEqual(item.battery_action, "idle")
            self.assertEqual(item.battery_kwh, 0.0)
            self.assertEqual(item.battery_energy_after_kwh, 100.0)

    def test_both_charge_and_discharge_forbidden(self):
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="no_charge_window",
                structured_adjustment={"hours": [12]},
                explanation="no charge",
            ),
            DirectiveInterpretationItem(
                note_index=1,
                applies=True,
                directive_type="no_discharge_window",
                structured_adjustment={"hours": [12]},
                explanation="no discharge",
            ),
        ]
        hours = _make_scenario()
        battery = _make_battery()
        compiled = compile_scenario_and_directives("TEST", hours, battery, directives)
        solution = solve_energy_optimization(compiled)
        plan = map_solution_to_hourly_plan(solution)
        self.assertEqual(plan[12].battery_action, "idle")
        self.assertEqual(plan[12].battery_kwh, 0.0)

    def test_deliberately_infeasible_scenario_raises_solver_error(self):
        """Demand 100, solar 0, battery rates 0, grid cap 50 -> impossible to meet demand."""
        hours = _make_scenario(demand_val=100.0, solar_val=0.0)
        battery = _make_battery(max_charge=0.0, max_discharge=0.0)
        directives = [
            DirectiveInterpretationItem(
                note_index=0,
                applies=True,
                directive_type="max_grid_window",
                structured_adjustment={"hours": [10], "max_grid_kwh": 50.0},
                explanation="cap impossible",
            )
        ]
        compiled = compile_scenario_and_directives("TEST", hours, battery, directives)
        with self.assertRaises(SolverError) as ctx:
            solve_energy_optimization(compiled)
        self.assertEqual(ctx.exception.code, "OPTIMIZATION_INFEASIBLE")

    def test_solver_timeout_handling(self):
        """Verify that solver honors solver_timeout_seconds and raises OPTIMIZATION_TIMEOUT."""
        hours = _make_scenario(demand_val=100.0, solar_val=20.0)
        battery = _make_battery()
        compiled = compile_scenario_and_directives("TEST", hours, battery, [])
        # Set an impossibly small timeout (e.g. 1e-9s) to trigger solver timeout
        compiled.solver_timeout_seconds = 1e-9
        with self.assertRaises(SolverError) as ctx:
            solve_energy_optimization(compiled)
        self.assertEqual(ctx.exception.code, "OPTIMIZATION_TIMEOUT")



if __name__ == "__main__":
    unittest.main()
