"""Factory function to build the configured LLM interpreter."""

from app.config import Settings
from app.llm.interface import LLMInterpreter
from app.llm.fake_provider import FakeInterpreter
from app.llm.gemini_provider import GeminiInterpreter
from app.llm.openai_provider import OpenAIInterpreter


def create_llm_interpreter(settings: Settings) -> LLMInterpreter:
    """Create and return the configured LLM interpreter instance."""
    provider = settings.llm_provider.lower()

    if provider == "fake":
        return FakeInterpreter()

    if provider == "gemini":
        return GeminiInterpreter(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider == "openai":
        return OpenAIInterpreter(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise ValueError(f"Unknown LLM provider '{settings.llm_provider}' configured")
