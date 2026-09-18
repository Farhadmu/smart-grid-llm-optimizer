"""Unit tests for deterministic guardrail validation of LLM outputs."""

import unittest
from app.llm.guardrails import validate_directive_interpretations, GuardrailValidationError


class TestGuardrails(unittest.TestCase):
    """Test every guardrail rejection and validation rule."""

    def test_valid_interpretations(self):
        raw = [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": [12, 13], "factor": 0.25},
                "explanation": "Valid solar reduction",
            },
            {
                "note_index": 1,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "Valid no op",
            },
        ]
        items = validate_directive_interpretations(raw, 2, battery_capacity_kwh=200.0)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].directive_type, "solar_reduction")
        self.assertEqual(items[0].structured_adjustment["factor"], 0.25)
        self.assertEqual(items[1].directive_type, "no_op")
        self.assertIsNone(items[1].structured_adjustment)

    def test_count_mismatch_rejected(self):
        raw = [{"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 2, 200.0)
        self.assertIn("count mismatch", str(ctx.exception).lower())

    def test_wrong_note_index_rejected(self):
        raw = [
            {"note_index": 1, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "x"},
            {"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "x"},
        ]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 2, 200.0)
        self.assertIn("order or invalid", str(ctx.exception).lower())

    def test_unsupported_directive_type_rejected(self):
        raw = [
            {
                "note_index": 0,
                "applies": True,
                "directive_type": "arbitrary_directive",
                "structured_adjustment": {"hours": [1, 2]},
                "explanation": "x",
            }
        ]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 1, 200.0)
        self.assertIn("unsupported directive_type", str(ctx.exception).lower())

    def test_applies_boolean_semantics_rejected(self):
        # no_op with applies=True
        raw1 = [{"note_index": 0, "applies": True, "directive_type": "no_op", "structured_adjustment": None, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw1, 1, 200.0)

        # active directive with applies=False
        raw2 = [{"note_index": 0, "applies": False, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [1]}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw2, 1, 200.0)

    def test_no_op_with_non_null_adjustment_rejected(self):
        raw = [{"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": {"hours": [1]}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw, 1, 200.0)

    def test_active_with_null_adjustment_rejected(self):
        raw = [{"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": None, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw, 1, 200.0)

    def test_hours_validation(self):
        # Empty hours
        raw_empty = [{"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": []}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_empty, 1, 200.0)

        # Out of bounds hour (24)
        raw_oob = [{"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [24]}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_oob, 1, 200.0)

        # Duplicate hours
        raw_dup = [{"note_index": 0, "applies": True, "directive_type": "no_charge_window", "structured_adjustment": {"hours": [10, 10]}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_dup, 1, 200.0)

    def test_solar_factor_bounds(self):
        # Factor > 1.0
        raw_high = [{"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [12], "factor": 1.2}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_high, 1, 200.0)

        # Factor < 0.0
        raw_neg = [{"note_index": 0, "applies": True, "directive_type": "solar_reduction", "structured_adjustment": {"hours": [12], "factor": -0.1}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_neg, 1, 200.0)

    def test_reserve_bounds_and_capacity_check(self):
        # Reserve > capacity
        raw_high = [{"note_index": 0, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [18], "minimum_energy_kwh": 250.0}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw_high, 1, battery_capacity_kwh=200.0)
        self.assertIn("exceeds battery capacity", str(ctx.exception).lower())

        # Negative reserve
        raw_neg = [{"note_index": 0, "applies": True, "directive_type": "minimum_battery_reserve", "structured_adjustment": {"hours": [18], "minimum_energy_kwh": -10.0}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_neg, 1, battery_capacity_kwh=200.0)

    def test_grid_cap_bounds(self):
        # Negative cap
        raw_neg = [{"note_index": 0, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [18], "max_grid_kwh": -150.0}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_neg, 1, 200.0)

        # Non-finite cap
        raw_nan = [{"note_index": 0, "applies": True, "directive_type": "max_grid_window", "structured_adjustment": {"hours": [18], "max_grid_kwh": float("nan")}, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_nan, 1, 200.0)

    def test_boolean_note_index_rejected(self):
        # note_index is True (boolean)
        raw = [{"note_index": True, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "x"}]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 1, 200.0)
        self.assertIn("not boolean", str(ctx.exception).lower())

    def test_missing_or_empty_explanation_rejected(self):
        # missing explanation
        raw_missing = [{"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None}]
        with self.assertRaises(GuardrailValidationError):
            validate_directive_interpretations(raw_missing, 1, 200.0)

        # empty / whitespace explanation
        raw_empty = [{"note_index": 0, "applies": False, "directive_type": "no_op", "structured_adjustment": None, "explanation": "   "}]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw_empty, 1, 200.0)
        self.assertIn("non-empty string", str(ctx.exception).lower())

    def test_extra_top_level_fields_rejected(self):
        raw = [{
            "note_index": 0,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "Valid",
            "unexpected_field": "injected",
        }]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 1, 200.0)
        self.assertIn("unexpected extra field", str(ctx.exception).lower())

    def test_extra_adjustment_keys_rejected(self):
        raw = [{
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [14, 15], "extra_key": 123},
            "explanation": "Valid",
        }]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 1, 200.0)
        self.assertIn("only 'hours'", str(ctx.exception).lower())

    def test_unsorted_hours_rejected(self):
        raw = [{
            "note_index": 0,
            "applies": True,
            "directive_type": "no_charge_window",
            "structured_adjustment": {"hours": [15, 14]},
            "explanation": "Unsorted hours",
        }]
        with self.assertRaises(GuardrailValidationError) as ctx:
            validate_directive_interpretations(raw, 1, 200.0)
        self.assertIn("sorted ascending", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
