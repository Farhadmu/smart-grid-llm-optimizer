"""OpenAI-compatible LLM provider implementation with strict structured JSON output."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import validate_directive_interpretations
from app.llm.prompt import (
    SYSTEM_INSTRUCTION,
    OPENAI_STRICT_RESPONSE_SCHEMA,
    build_user_prompt,
)
from app.models.schemas import DirectiveInterpretationItem


class OpenAIInterpreter(LLMInterpreter):
    """Real LLM interpreter for OpenAI, Groq, Ollama, DeepSeek, OpenRouter, etc."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 8.0,
        strict_schema: bool = True,
        transport: Optional[Callable[[urllib.request.Request, float], str]] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.strict_schema = strict_schema
        self.transport = transport or self._default_transport

    def _default_transport(self, req: urllib.request.Request, timeout: float) -> str:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_bytes = resp.read()
            return resp_bytes.decode("utf-8")

    def build_request(self, user_prompt: str) -> urllib.request.Request:
        """Construct the HTTP request for OpenAI chat completions."""
        url = f"{self.base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }

        if self.strict_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "gridwise_directives",
                    "strict": True,
                    "schema": OPENAI_STRICT_RESPONSE_SCHEMA,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        return urllib.request.Request(url, data=body, headers=headers, method="POST")

    def _call_openai_sync(self, prompt: str) -> str:
        """Synchronous call using configured transport."""
        req = self.build_request(prompt)

        try:
            raw_response = self.transport(req, self.timeout_seconds)
            data = json.loads(raw_response)
            if not isinstance(data, dict):
                raise LLMInterpretationError("Unexpected non-dictionary root in OpenAI API response")

            choices = data.get("choices")
            if not isinstance(choices, list) or len(choices) == 0:
                raise LLMInterpretationError("No choices returned by OpenAI model")

            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise LLMInterpretationError("Malformed choice in OpenAI response")

            message = first_choice.get("message")
            if not isinstance(message, dict):
                raise LLMInterpretationError("Malformed message in OpenAI choice")

            content = message.get("content")
            if content is None:
                raise LLMInterpretationError("Missing content in OpenAI message")

            return str(content)

        except urllib.error.HTTPError as e:
            raise LLMInterpretationError(f"OpenAI API HTTP Error {e.code}: {e.reason}") from None
        except urllib.error.URLError as e:
            raise LLMInterpretationError(f"OpenAI API connection error: {e.reason}") from None
        except json.JSONDecodeError as e:
            raise LLMInterpretationError(f"Failed to parse OpenAI provider response as JSON: {str(e)}") from None
        except LLMInterpretationError:
            raise
        except Exception as e:
            raise LLMInterpretationError(f"OpenAI API call failed: {type(e).__name__}") from None

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
            raise LLMInterpretationError("OPENAI_API_KEY is not configured")

        user_prompt = build_user_prompt(notes, battery_capacity_kwh, feedback_error)
        raw_text = await asyncio.to_thread(self._call_openai_sync, user_prompt)
        return self.parse_model_text(raw_text, len(notes), battery_capacity_kwh)
