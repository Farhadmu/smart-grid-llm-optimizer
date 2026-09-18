"""Concurrency and scenario isolation tests."""

import asyncio
import json
import os
import unittest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")

from app.main import app
from tests.test_api import asgi_call


def _make_scenario(scenario_id: str, demand_multiplier: float = 1.0):
    return {
        "scenario_id": scenario_id,
        "operator_notes": ["The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."],
        "hours": [
            {
                "hour": h,
                "demand_kwh": round(40.0 * demand_multiplier, 2),
                "solar_kwh": 10.0,
                "tariff_bdt_per_kwh": 8.0,
            }
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 20.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        },
    }


class TestConcurrencyAndIsolation(unittest.TestCase):
    """Verify isolation and concurrency behavior."""

    def test_concurrent_requests_isolation(self):
        async def run_concurrent():
            scenarios = [
                _make_scenario(f"CONCUR-{i}", demand_multiplier=1.0 + i * 0.2)
                for i in range(5)
            ]
            tasks = [
                asgi_call("POST", "/optimize-energy", body=sc)
                for sc in scenarios
            ]
            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.run(run_concurrent())
        self.assertEqual(len(results), 5)

        for i, (status, headers, body) in enumerate(results):
            self.assertEqual(status, 200)
            expected_id = f"CONCUR-{i}"
            self.assertEqual(body["scenario_id"], expected_id)
            self.assertEqual(len(body["hourly_plan"]), 24)

    def test_repeated_requests_idempotence(self):
        scenario = _make_scenario("REPEAT-TEST", demand_multiplier=1.5)

        async def run_repeated():
            res1 = await asgi_call("POST", "/optimize-energy", body=scenario)
            res2 = await asgi_call("POST", "/optimize-energy", body=scenario)
            return res1, res2

        (s1, _, b1), (s2, _, b2) = asyncio.run(run_repeated())
        self.assertEqual(s1, 200)
        self.assertEqual(s2, 200)
        self.assertEqual(b1["total_cost_bdt"], b2["total_cost_bdt"])
        self.assertEqual(b1["total_grid_kwh"], b2["total_grid_kwh"])
        self.assertEqual(b1["peak_grid_kwh"], b2["peak_grid_kwh"])


if __name__ == "__main__":
    unittest.main()
