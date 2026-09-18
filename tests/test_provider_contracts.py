"""Mocked transport tests asserting Gemini and OpenAI request/response contracts."""

import json
import unittest
import urllib.request
from app.llm.gemini_provider import GeminiInterpreter
from app.llm.openai_provider import OpenAIInterpreter
from app.llm.interface import LLMInterpretationError


class TestProviderContracts(unittest.TestCase):
    """Assert exact outgoing payloads and safe response parsing without network calls."""

    def test_gemini_outgoing_payload_contract(self):
        captured_req = None

        def mock_transport(req: urllib.request.Request, timeout: float) -> str:
            nonlocal captured_req
            captured_req = req
            # Return valid Gemini mock response
            return json.dumps({
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({
                                        "directive_interpretation": [
                                            {
                                                "note_index": 0,
                                                "applies": True,
                                                "directive_type": "no_charge_window",
                                                "structured_adjustment": {"hours": [2, 3]},
                                                "explanation": "No charging",
                                            }
                                        ]
                                    })
                                }
                            ]
                        }
                    }
                ]
            })

        interpreter = GeminiInterpreter(
            api_key="mock-gemini-key-12345",
            model="gemini-1.5-flash",
            transport=mock_transport,
        )

        req = interpreter.build_request("Test prompt")
        # 1. Assert API key is passed via header, NOT query parameter
        self.assertNotIn("?key=", req.full_url)
        self.assertEqual(req.headers.get("X-goog-api-key"), "mock-gemini-key-12345")
        self.assertEqual(req.headers.get("Content-type"), "application/json")

        # 2. Assert generationConfig schema structure
        payload = json.loads(req.data.decode("utf-8"))
        gen_cfg = payload["generationConfig"]
        self.assertEqual(gen_cfg["responseMimeType"], "application/json")
        self.assertIn("responseJsonSchema", gen_cfg)
        self.assertEqual(gen_cfg["responseJsonSchema"]["type"], "OBJECT")

        # 3. Assert successful call and parsing
        items = interpreter.parse_model_text(
            mock_transport(req, 8.0).split('"text": ')[1].rsplit("}]", 2)[0].strip('"').replace('\\"', '"'),
            notes_count=1,
            battery_capacity_kwh=200.0,
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].directive_type, "no_charge_window")

    def test_openai_strict_schema_outgoing_payload(self):
        captured_req = None

        def mock_transport(req: urllib.request.Request, timeout: float) -> str:
            nonlocal captured_req
            captured_req = req
            return json.dumps({
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "directive_interpretation": [
                                    {
                                        "note_index": 0,
                                        "applies": False,
                                        "directive_type": "no_op",
                                        "structured_adjustment": None,
                                        "explanation": "No op",
                                    }
                                ]
                            })
                        }
                    }
                ]
            })

        interpreter = OpenAIInterpreter(
            api_key="mock-openai-key-abcde",
            strict_schema=True,
            transport=mock_transport,
        )

        req = interpreter.build_request("Test prompt")
        self.assertEqual(req.headers.get("Authorization"), "Bearer mock-openai-key-abcde")

        payload = json.loads(req.data.decode("utf-8"))
        self.assertIn("response_format", payload)
        rf = payload["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertTrue(rf["json_schema"]["strict"])
        self.assertEqual(rf["json_schema"]["schema"]["type"], "object")

    def test_openai_compatibility_mode_payload(self):
        interpreter = OpenAIInterpreter(
            api_key="mock-key",
            strict_schema=False,
        )
        req = interpreter.build_request("Test prompt")
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_provider_returns_direct_json_list(self):
        """Model directly returns a JSON list instead of a wrapper object."""
        interpreter = GeminiInterpreter(api_key="dummy")
        list_json = json.dumps([
            {
                "note_index": 0,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "No op directive",
            }
        ])
        items = interpreter.parse_model_text(list_json, notes_count=1, battery_capacity_kwh=200.0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].directive_type, "no_op")

    def test_provider_returns_scalar_or_null_raises_controlled_error(self):
        """Model returns invalid root types (int, string, null)."""
        interpreter = GeminiInterpreter(api_key="dummy")
        with self.assertRaises(LLMInterpretationError) as ctx1:
            interpreter.parse_model_text("123", notes_count=1, battery_capacity_kwh=200.0)
        self.assertIn("Expected JSON object or array", str(ctx1.exception))

        with self.assertRaises(LLMInterpretationError) as ctx2:
            interpreter.parse_model_text("null", notes_count=1, battery_capacity_kwh=200.0)
        self.assertIn("Expected JSON object or array", str(ctx2.exception))

        with self.assertRaises(LLMInterpretationError) as ctx3:
            interpreter.parse_model_text('"just a string"', notes_count=1, battery_capacity_kwh=200.0)
        self.assertIn("Expected JSON object or array", str(ctx3.exception))

    def test_provider_missing_directive_interpretation_key_raises_controlled_error(self):
        interpreter = GeminiInterpreter(api_key="dummy")
        with self.assertRaises(LLMInterpretationError) as ctx:
            interpreter.parse_model_text(json.dumps({"some_other_key": []}), notes_count=1, battery_capacity_kwh=200.0)
        self.assertIn("missing 'directive_interpretation' key", str(ctx.exception))

    def test_gemini_model_normalization(self):
        """Assert models/ prefix and human aliases are strictly normalized to gemini-2.5-flash."""
        interpreter1 = GeminiInterpreter(api_key="dummy", model="models/gemini-2.5-flash")
        self.assertEqual(interpreter1.model, "gemini-2.5-flash")

        interpreter2 = GeminiInterpreter(api_key="dummy", model="flash 2.5")
        self.assertEqual(interpreter2.model, "gemini-2.5-flash")

        interpreter3 = GeminiInterpreter(api_key="dummy", model="models/gemini-1.5-flash")
        self.assertEqual(interpreter3.model, "gemini-2.5-flash")

    def test_gemini_single_model_lock_and_rate_limit_handling(self):
        """Assert that the provider uses only gemini-2.5-flash and handles 429 without model hopping."""
        import urllib.error
        calls = []

        def mock_rate_limit_transport(req: urllib.request.Request, timeout: float) -> str:
            calls.append(req.full_url)
            raise urllib.error.HTTPError(
                url=req.full_url, code=429, msg="Too Many Requests", hdrs={}, fp=None
            )

        interpreter = GeminiInterpreter(
            api_key="dummy",
            model="gemini-2.5-flash",
            transport=mock_rate_limit_transport,
        )

        with self.assertRaises(LLMInterpretationError) as ctx:
            interpreter._call_gemini_sync("Hello")

        self.assertIn("rate limit exceeded (HTTP 429)", str(ctx.exception))
        # Verify exactly one call was made without candidate model hopping
        self.assertEqual(len(calls), 1)
        self.assertIn("gemini-2.5-flash", calls[0])

    def test_gemini_transient_503_error_handling(self):
        """Assert that transient 503 errors raise controlled LLMInterpretationError."""
        import urllib.error
        def mock_503_transport(req: urllib.request.Request, timeout: float) -> str:
            raise urllib.error.HTTPError(
                url=req.full_url, code=503, msg="Service Unavailable", hdrs={}, fp=None
            )

        interpreter = GeminiInterpreter(
            api_key="dummy",
            model="gemini-2.5-flash",
            transport=mock_503_transport,
        )

        with self.assertRaises(LLMInterpretationError) as ctx:
            interpreter._call_gemini_sync("Hello")

        self.assertIn("temporarily unavailable (HTTP 503)", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
