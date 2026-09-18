"""Google Gemini API provider implementation with structured JSON output."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import validate_directive_interpretations
from app.llm.prompt import SYSTEM_INSTRUCTION, DIRECTIVE_SCHEMA, build_user_prompt
from app.models.schemas import DirectiveInterpretationItem


class GeminiInterpreter(LLMInterpreter):
    """Real LLM interpreter communicating with Google Gemini REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout_seconds: float = 8.0,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _call_gemini_sync(self, prompt: str) -> str:
        """Synchronous HTTP POST to Gemini generateContent endpoint."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": DIRECTIVE_SCHEMA,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_bytes = resp.read()
                data = json.loads(resp_bytes.decode("utf-8"))
                # Extract text
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMInterpretationError("No candidates returned by Gemini model")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMInterpretationError("Empty parts returned by Gemini model")
                return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", "ignore")
            # Do not leak secrets in exception
            raise LLMInterpretationError(f"Gemini API HTTP Error {e.code}: {e.reason}") from None
        except urllib.error.URLError as e:
            raise LLMInterpretationError(f"Gemini API connection error: {e.reason}") from None
        except Exception as e:
            raise LLMInterpretationError(f"Gemini API call failed: {type(e).__name__}") from None

    async def interpret_notes(
        self,
        notes: List[str],
        battery_capacity_kwh: float,
        scenario_id: str,
        correlation_id: str = "",
        feedback_error: Optional[str] = None,
    ) -> List[DirectiveInterpretationItem]:
        if not self.api_key:
            raise LLMInterpretationError("GEMINI_API_KEY is not configured")

        user_prompt = build_user_prompt(notes, battery_capacity_kwh, feedback_error)

        raw_text = await asyncio.to_thread(self._call_gemini_sync, user_prompt)

        try:
            parsed = json.loads(raw_text)
        except Exception as e:
            raise LLMInterpretationError(f"Model output is not valid JSON: {str(e)}", raw_output=raw_text)

        raw_items = parsed.get("directive_interpretation")
        if raw_items is None and isinstance(parsed, list):
            raw_items = parsed

        if not isinstance(raw_items, list):
            raise LLMInterpretationError(
                "Model JSON missing 'directive_interpretation' list", raw_output=raw_text
            )

        return validate_directive_interpretations(raw_items, len(notes), battery_capacity_kwh)
