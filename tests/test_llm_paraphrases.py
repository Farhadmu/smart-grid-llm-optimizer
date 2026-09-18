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

    def test_paraphrase_solar_cut_by_30_percent(self):
        """'cut by 30%' -> usable factor 0.70."""
        notes = ["Rooftop solar output will be cut by 30% between 1 PM and 3 PM due to dust storms."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P01")
        )
        self.assertEqual(res[0].directive_type, "solar_reduction")
        self.assertAlmostEqual(res[0].structured_adjustment["factor"], 0.70, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [13, 14])

    def test_paraphrase_solar_only_20_percent_should_count(self):
        """'only 20% should count' -> usable factor 0.20."""
        notes = ["Due to panel shading, only 20% should count from 11 AM until 1 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P02")
        )
        self.assertEqual(res[0].directive_type, "solar_reduction")
        self.assertAlmostEqual(res[0].structured_adjustment["factor"], 0.20, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [11, 12])

    def test_paraphrase_solar_roughly_half_normal_output(self):
        """'roughly half of normal output' -> usable factor 0.50."""
        notes = ["Cloud cover will yield roughly half of normal output between 3 PM and 6 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P03")
        )
        self.assertEqual(res[0].directive_type, "solar_reduction")
        self.assertAlmostEqual(res[0].structured_adjustment["factor"], 0.50, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [15, 16, 17])

    def test_paraphrase_reserve_40_percent_capacity(self):
        """'keep at least 40% of battery capacity' on 200 kWh -> 80.0 kWh reserve."""
        notes = ["Keep at least 40% of battery capacity in reserve from 6 PM until 9 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P04")
        )
        self.assertEqual(res[0].directive_type, "minimum_battery_reserve")
        self.assertAlmostEqual(res[0].structured_adjustment["minimum_energy_kwh"], 80.0, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [18, 19, 20])

    def test_paraphrase_reserve_no_less_than_120_kwh(self):
        """'no less than 120 kWh' -> 120.0 kWh reserve."""
        notes = ["The battery must maintain no less than 120 kWh from 5 PM to 8 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P05")
        )
        self.assertEqual(res[0].directive_type, "minimum_battery_reserve")
        self.assertAlmostEqual(res[0].structured_adjustment["minimum_energy_kwh"], 120.0, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [17, 18, 19])

    def test_paraphrase_no_charge_accept_no_additional_energy(self):
        """'must not accept any additional energy' -> no_charge_window."""
        notes = ["The energy storage system must not accept any additional energy between 2 PM and 5 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P06")
        )
        self.assertEqual(res[0].directive_type, "no_charge_window")
        self.assertEqual(res[0].structured_adjustment["hours"], [14, 15, 16])

    def test_paraphrase_no_charge_charging_prohibited_or_unavailable(self):
        """'battery charging is prohibited' & 'charging unavailable' -> no_charge_window."""
        notes = [
            "Battery charging is prohibited from 1 PM until 3 PM.",
            "Substation maintenance makes charging unavailable between 3 PM and 6 PM.",
        ]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P07")
        )
        self.assertEqual(res[0].directive_type, "no_charge_window")
        self.assertEqual(res[0].structured_adjustment["hours"], [13, 14])
        self.assertEqual(res[1].directive_type, "no_charge_window")
        self.assertEqual(res[1].structured_adjustment["hours"], [15, 16, 17])

    def test_paraphrase_no_discharge_cannot_discharge(self):
        """'cannot discharge energy' -> no_discharge_window."""
        notes = ["The battery cannot discharge energy during the 5 PM to 7 PM protection window."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P08")
        )
        self.assertEqual(res[0].directive_type, "no_discharge_window")
        self.assertEqual(res[0].structured_adjustment["hours"], [17, 18])

    def test_paraphrase_grid_cap_stay_below_and_no_more_than(self):
        """'must stay below 180 kWh' & 'no more than 90 kWh' -> max_grid_window."""
        notes = [
            "Campus intake must stay below 180 kWh from 6 PM until 9 PM.",
            "Grid intake can be no more than 90 kWh between 11 AM and 2 PM.",
        ]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P09")
        )
        self.assertEqual(res[0].directive_type, "max_grid_window")
        self.assertAlmostEqual(res[0].structured_adjustment["max_grid_kwh"], 180.0, places=2)
        self.assertEqual(res[0].structured_adjustment["hours"], [18, 19, 20])
        self.assertEqual(res[1].directive_type, "max_grid_window")
        self.assertAlmostEqual(res[1].structured_adjustment["max_grid_kwh"], 90.0, places=2)
        self.assertEqual(res[1].structured_adjustment["hours"], [11, 12, 13])

    def test_paraphrase_through_9_pm_window(self):
        """'through 9 PM' in evening peak context -> [18, 19, 20]."""
        notes = ["Feeder constraints require grid import to stay below 150 kWh through 9 PM."]
        res = asyncio.run(
            self.interpreter.interpret_notes(notes, battery_capacity_kwh=200.0, scenario_id="TEST-P10")
        )
        self.assertEqual(res[0].directive_type, "max_grid_window")
        self.assertEqual(res[0].structured_adjustment["hours"], [18, 19, 20])


if __name__ == "__main__":
    unittest.main()
