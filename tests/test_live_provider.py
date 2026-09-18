"""Opt-in live LLM provider verification tests.

These tests only run when RUN_LIVE_LLM_TESTS is set to "1" or "true" in the environment.
They verify actual live end-to-end communication with the configured provider (Gemini or OpenAI).
"""

import asyncio
import os
import unittest
from app.config import get_settings
from app.llm.factory import create_llm_interpreter


class TestLiveProvider(unittest.TestCase):
    """Opt-in live provider verification tests."""

    def setUp(self):
        self.settings = get_settings()
        if not self.settings.run_live_llm_tests:
            self.skipTest(
                "Skipping live LLM test: RUN_LIVE_LLM_TESTS is not enabled."
            )
        if self.settings.llm_provider not in ("gemini", "openai"):
            self.skipTest(
                f"Skipping live LLM test: provider '{self.settings.llm_provider}' is not a real API provider."
            )

    def test_live_provider_interpretation(self):
        """Execute a live structured output request against the configured provider."""
        client = create_llm_interpreter(self.settings)
        scenario_id = "LIVE-TEST-01"
        notes = ["The battery charging circuit will be disconnected between 2 PM and 4 PM."]
        directives = asyncio.run(
            client.interpret_notes(
                notes=notes,
                battery_capacity_kwh=200.0,
                scenario_id=scenario_id,
            )
        )

        self.assertEqual(len(directives), 1)
        item = directives[0]
        self.assertEqual(item.note_index, 0)
        self.assertTrue(item.applies)
        self.assertEqual(item.directive_type, "no_charge_window")
        self.assertIsNotNone(item.structured_adjustment)
        self.assertIn(14, item.structured_adjustment.get("hours", []))
        self.assertIn(15, item.structured_adjustment.get("hours", []))


if __name__ == "__main__":
    unittest.main()
