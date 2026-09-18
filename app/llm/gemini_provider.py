"""Google Gemini API provider implementation with strict structured JSON output."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import validate_directive_interpretations
from app.llm.prompt import SYSTEM_INSTRUCTION, GEMINI_RESPONSE_SCHEMA, build_user_prompt
from app.models.schemas import DirectiveInterpretationItem


def normalize_gemini_model(model_name: Optional[str]) -> str:
    """Ensure Gemini model identifier adheres to valid Google API format."""
    cleaned = (model_name or "").strip()
    if cleaned.startswith("models/"):
        cleaned = cleaned.removeprefix("models/")
    
    cleaned_lower = cleaned.lower().replace(" ", "-")
    if cleaned_lower in ("flash-2.5", "2.5-flash", "gemini-flash-2.5", "gemini-2.5", "2.5"):
        return "gemini-2.5-flash"
    if cleaned_lower in ("flash-1.5", "1.5-flash", "gemini-flash-1.5", "gemini-1.5", "1.5"):
        return "gemini-1.5-flash"
    if cleaned_lower in ("flash-2.0", "2.0-flash", "gemini-flash-2.0", "gemini-2.0", "2.0"):
        return "gemini-2.0-flash"
    
    return cleaned or "gemini-2.5-flash"


class GeminiInterpreter(LLMInterpreter):
    """Real LLM interpreter communicating with Google Gemini REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout_seconds: float = 8.0,
        transport: Optional[Callable[[urllib.request.Request, float], str]] = None,
    ):
        self.api_key = api_key
        self.model = normalize_gemini_model(model)
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._default_transport

    def _default_transport(self, req: urllib.request.Request, timeout: float) -> str:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_bytes = resp.read()
            return resp_bytes.decode("utf-8")

    def build_request(self, user_prompt: str, model_override: Optional[str] = None) -> urllib.request.Request:
        """Construct the Gemini REST API Request object without secrets in the URL."""
        model = normalize_gemini_model(model_override or self.model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseJsonSchema": GEMINI_RESPONSE_SCHEMA,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        return urllib.request.Request(url, data=body, headers=headers, method="POST")

    def _call_gemini_sync(self, prompt: str) -> str:
        """Synchronous call using configured transport with resilient model fallback."""
        models_to_try = [self.model]
        for candidate in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        last_error: Optional[Exception] = None
        for current_model in models_to_try:
            req = self.build_request(prompt, model_override=current_model)
            try:
                raw_response = self.transport(req, self.timeout_seconds)
                data = json.loads(raw_response)
                if not isinstance(data, dict):
                    raise LLMInterpretationError("Unexpected non-dictionary root in Gemini API response")

                candidates = data.get("candidates")
                if not isinstance(candidates, list) or len(candidates) == 0:
                    raise LLMInterpretationError("No candidates returned by Gemini model")

                candidate = candidates[0]
                if not isinstance(candidate, dict):
                    raise LLMInterpretationError("Malformed candidate in Gemini API response")

                content = candidate.get("content")
                if not isinstance(content, dict):
                    raise LLMInterpretationError("Malformed content in Gemini candidate")

                parts = content.get("parts")
                if not isinstance(parts, list) or len(parts) == 0:
                    raise LLMInterpretationError("Empty parts in Gemini content")

                part = parts[0]
                if not isinstance(part, dict) or "text" not in part:
                    raise LLMInterpretationError("Missing text in Gemini response part")

                return str(part["text"])

            except urllib.error.HTTPError as e:
                # If 404 (model not found) and another fallback candidate is available, retry
                if e.code == 404 and current_model != models_to_try[-1]:
                    last_error = LLMInterpretationError(
                        f"Gemini API HTTP Error {e.code}: {e.reason} for model '{current_model}'"
                    )
                    continue
                # Safe exception without leaking API key
                raise LLMInterpretationError(f"Gemini API HTTP Error {e.code}: {e.reason}") from None
            except urllib.error.URLError as e:
                raise LLMInterpretationError(f"Gemini API connection error: {e.reason}") from None
            except json.JSONDecodeError as e:
                raise LLMInterpretationError(f"Failed to parse Gemini provider response as JSON: {str(e)}") from None
            except LLMInterpretationError:
                raise
            except Exception as e:
                raise LLMInterpretationError(f"Gemini API call failed: {type(e).__name__}") from None

        if last_error:
            raise last_error
        raise LLMInterpretationError("Gemini API call failed: all model attempts exhausted")

    def parse_model_text(
        self, raw_text: str, notes_count: int, battery_capacity_kwh: float
    ) -> List[DirectiveInterpretationItem]:
        """Safely parse and validate model JSON output."""
        try:
            parsed = json.loads(raw_text)
        except Exception as e:
            raise LLMInterpretationError(f"Model output is not valid JSON: {str(e)}", raw_output=raw_text)

        if isinstance(parsed, dict):
            raw_items = parsed.get("directive_interpretation")
            if raw_items is None:
                raise LLMInterpretationError(
                    "Model JSON object missing 'directive_interpretation' key", raw_output=raw_text
                )
        elif isinstance(parsed, list):
            raw_items = parsed
        else:
            raise LLMInterpretationError(
                f"Expected JSON object or array from model, got {type(parsed).__name__}", raw_output=raw_text
            )

        if not isinstance(raw_items, list):
            raise LLMInterpretationError(
                f"'directive_interpretation' must be a list, got {type(raw_items).__name__}", raw_output=raw_text
            )

        return validate_directive_interpretations(raw_items, notes_count, battery_capacity_kwh)

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
        return self.parse_model_text(raw_text, len(notes), battery_capacity_kwh)
