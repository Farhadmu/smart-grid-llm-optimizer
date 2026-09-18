"""OpenAI-compatible LLM provider implementation with structured JSON output."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import validate_directive_interpretations
from app.llm.prompt import SYSTEM_INSTRUCTION, build_user_prompt
from app.models.schemas import DirectiveInterpretationItem


class OpenAIInterpreter(LLMInterpreter):
    """Real LLM interpreter for OpenAI, Groq, Ollama, DeepSeek, OpenRouter, etc."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 8.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _call_openai_sync(self, prompt: str) -> str:
        """Synchronous HTTP POST to chat/completions endpoint."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_bytes = resp.read()
                data = json.loads(resp_bytes.decode("utf-8"))
                choices = data.get("choices", [])
                if not choices:
                    raise LLMInterpretationError("No choices returned by OpenAI model")
                return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as e:
            raise LLMInterpretationError(f"OpenAI API HTTP Error {e.code}: {e.reason}") from None
        except urllib.error.URLError as e:
            raise LLMInterpretationError(f"OpenAI API connection error: {e.reason}") from None
        except Exception as e:
            raise LLMInterpretationError(f"OpenAI API call failed: {type(e).__name__}") from None

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
