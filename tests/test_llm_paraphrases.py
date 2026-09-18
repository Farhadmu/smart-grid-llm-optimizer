"""Tests for LLM interpretation of paraphrases, times, percentages, and directive types."""

import asyncio
import unittest
from app.llm.fake_provider import FakeInterpreter


class TestLLMParaphrases(unittest.TestCase):
    """Verify linguistic parsing, time windows, and percentage conversions."""

    def setUp(self):
        self.interpreter = FakeInterpreter()

    def test_solar_80_percent_reduction_becomes_factor_0_2(self):
        """Prove that '80% reduction' maps to remaining usable factor 0.2."""
        notes = ["Expect an 80% reduction in rooftop solar between 11 AM and 2 PM because of inverter work."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-01")
        )
        self.assertEqual(len(res), 1)
        item = res[0]
        self.assertEqual(item.directive_type, "solar_reduction")
        self.assertTrue(item.applies)
        self.assertEqual(item.structured_adjustment["hours"], [11, 12, 13])
        self.assertAlmostEqual(item.structured_adjustment["factor"], 0.20, places=4)

    def test_solar_reduced_to_25_percent(self):
        notes = ["During cleaning from noon until 2 PM, usable solar should be treated as roughly 25% of the forecast."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-02")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "solar_reduction")
        self.assertEqual(item.structured_adjustment["hours"], [12, 13])
        self.assertAlmostEqual(item.structured_adjustment["factor"], 0.25, places=4)

    def test_solar_fraction_half_output(self):
        notes = ["Cloud cover will leave about half of the forecast solar output from 10 AM until noon."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-03")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "solar_reduction")
        self.assertEqual(item.structured_adjustment["hours"], [10, 11])
        self.assertAlmostEqual(item.structured_adjustment["factor"], 0.50, places=4)

    def test_capacity_relative_battery_reserve_sample_03(self):
        """Prove that 50% of 200 kWh battery capacity maps to 100.0 kWh minimum energy."""
        notes = ["Keep at least 50% of the battery capacity stored in the battery from 6 PM until 9 PM for emergency operations."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-04")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "minimum_battery_reserve")
        self.assertTrue(item.applies)
        self.assertEqual(item.structured_adjustment["hours"], [18, 19, 20])
        self.assertAlmostEqual(item.structured_adjustment["minimum_energy_kwh"], 100.0, places=2)

    def test_absolute_battery_reserve(self):
        notes = ["Keep at least 90 kWh in the battery from 6 PM until 10 PM for emergency services."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-05")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "minimum_battery_reserve")
        self.assertEqual(item.structured_adjustment["hours"], [18, 19, 20, 21])
        self.assertAlmostEqual(item.structured_adjustment["minimum_energy_kwh"], 90.0, places=2)

    def test_no_charge_window(self):
        notes = ["The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-06")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "no_charge_window")
        self.assertTrue(item.applies)
        self.assertEqual(item.structured_adjustment["hours"], [2, 3, 4])

    def test_no_discharge_window(self):
        notes = ["For protection testing, the battery must not discharge from 6 PM until 8 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-07")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "no_discharge_window")
        self.assertTrue(item.applies)
        self.assertEqual(item.structured_adjustment["hours"], [18, 19])

    def test_max_grid_window(self):
        notes = ["From 6 PM until 9 PM, campus grid import must not exceed 155 kWh in any hour because the feeder is operating under a temporary limit."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-08")
        )
        item = res[0]
        self.assertEqual(item.directive_type, "max_grid_window")
        self.assertTrue(item.applies)
        self.assertEqual(item.structured_adjustment["hours"], [18, 19, 20])
        self.assertAlmostEqual(item.structured_adjustment["max_grid_kwh"], 155.0, places=2)

    def test_distractor_notes_map_to_no_op(self):
        distractors = [
            "The sports office moved next month's registration deadline.",
            "The library is extending book-return hours next week.",
            "The student affairs office will publish club notices tomorrow.",
            "A seminar room booking was moved to next week.",
        ]
        res = asyncio.run(
            self.interpreter.interpret_notes(distractors, battery_capacity_kwh=200.0, scenario_id="TEST-09")
        )
        self.assertEqual(len(res), 4)
        for i, item in enumerate(res):
            self.assertEqual(item.note_index, i)
            self.assertEqual(item.directive_type, "no_op")
            self.assertFalse(item.applies)
            self.assertIsNone(item.structured_adjustment)

    def test_multi_note_ordering(self):
        notes = [
            "Cloud cover during panel inspection will leave about half of the forecast solar output from 10 AM until noon.",
            "The charging circuit will be unavailable from 2 PM until 4 PM.",
            "The library is extending book-return hours next week.",
        ]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-10")
        )
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0].note_index, 0)
        self.assertEqual(res[0].directive_type, "solar_reduction")
        self.assertEqual(res[1].note_index, 1)
        self.assertEqual(res[1].directive_type, "no_charge_window")
        self.assertEqual(res[2].note_index, 2)
        self.assertEqual(res[2].directive_type, "no_op")


if __name__ == "__main__":
    unittest.main()
