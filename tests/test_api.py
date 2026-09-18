"""API integration tests for GET /health and POST /optimize-energy."""

import asyncio
import json
import os
import unittest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")

from app.main import app
from app.models.schemas import ErrorEnvelope


async def asgi_call(method: str, path: str, body=None, headers=None):
    headers = headers or {}
    raw_headers = [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in headers.items()]
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    if body is not None and b"content-type" not in [h[0] for h in raw_headers]:
        raw_headers.append((b"content-type", b"application/json"))

    response_messages = []
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": raw_headers,
        "app": app,
    }

    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        response_messages.append(message)

    await app(scope, receive, send)

    status_code = None
    resp_headers = {}
    resp_body = b""
    for m in response_messages:
        if m["type"] == "http.response.start":
            status_code = m["status"]
            for k, v in m.get("headers", []):
                resp_headers[k.decode("latin1")] = v.decode("latin1")
        elif m["type"] == "http.response.body":
            resp_body += m.get("body", b"")

    parsed_body = json.loads(resp_body.decode("utf-8")) if resp_body else None
    return status_code, resp_headers, parsed_body


class TestAPIEndpoints(unittest.TestCase):
    """Integration test suite for HTTP API."""

    def test_health_endpoint(self):
        status, headers, body = asyncio.run(asgi_call("GET", "/health"))
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})
        self.assertIn("x-correlation-id", [k.lower() for k in headers.keys()])

    def test_successful_optimize_energy(self):
        payload = {
            "scenario_id": "API-TEST-01",
            "operator_notes": ["The charging circuit will be unavailable from 2 PM until 4 PM."],
            "hours": [
                {"hour": h, "demand_kwh": 50.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 10.0}
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
        status, headers, body = asyncio.run(asgi_call("POST", "/optimize-energy", body=payload))
        self.assertEqual(status, 200)
        self.assertEqual(body["scenario_id"], "API-TEST-01")
        self.assertEqual(len(body["hourly_plan"]), 24)
        self.assertEqual(len(body["directive_interpretation"]), 1)
        self.assertEqual(body["directive_interpretation"][0]["directive_type"], "no_charge_window")
        self.assertIn("total_grid_kwh", body)
        self.assertIn("total_cost_bdt", body)
        self.assertIn("peak_grid_kwh", body)
        self.assertIn("plan_summary", body)

    def test_custom_correlation_id_preserved(self):
        corr_id = "test-corr-id-12345"
        status, headers, body = asyncio.run(
            asgi_call("GET", "/health", headers={"X-Correlation-ID": corr_id})
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-correlation-id"), corr_id)

    def test_missing_field_returns_400_with_error_envelope(self):
        # Missing battery
        payload = {
            "scenario_id": "API-TEST-MISSING",
            "operator_notes": ["Note"],
            "hours": [
                {"hour": h, "demand_kwh": 50.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 10.0}
                for h in range(24)
            ],
        }
        status, headers, body = asyncio.run(asgi_call("POST", "/optimize-energy", body=payload))
        self.assertIn(status, (400, 422))
        self.assertIn("error", body)
        self.assertIn("code", body["error"])
        self.assertIn("message", body["error"])

    def test_semantic_error_returns_422_with_error_envelope(self):
        # initial_energy > capacity
        payload = {
            "scenario_id": "API-TEST-INVALID-BATTERY",
            "operator_notes": ["Note"],
            "hours": [
                {"hour": h, "demand_kwh": 50.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 10.0}
                for h in range(24)
            ],
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 250.0,  # Invalid!
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 50.0,
                "max_discharge_kwh_per_hour": 50.0,
            },
        }
        status, headers, body = asyncio.run(asgi_call("POST", "/optimize-energy", body=payload))
        self.assertEqual(status, 422)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "SEMANTIC_VALIDATION_ERROR")

    def test_infeasible_scenario_returns_controlled_error(self):
        # Infeasible grid cap
        payload = {
            "scenario_id": "API-TEST-INFEASIBLE",
            "operator_notes": ["Never draw more than 10 kWh from the grid between 10 AM and 11 AM."],
            "hours": [
                {"hour": h, "demand_kwh": 100.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 10.0}
                for h in range(24)
            ],
            "battery": {
                "capacity_kwh": 200.0,
                "initial_energy_kwh": 100.0,
                "minimum_energy_kwh": 20.0,
                "max_charge_kwh_per_hour": 0.0,
                "max_discharge_kwh_per_hour": 0.0,
            },
        }
        status, headers, body = asyncio.run(asgi_call("POST", "/optimize-energy", body=payload))
        self.assertEqual(status, 500)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "OPTIMIZATION_INFEASIBLE")



if __name__ == "__main__":
    unittest.main()
