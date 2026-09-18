"""Configuration settings for GridWise service."""

import os
from typing import Literal
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # LLM settings: default to fake if no API key is set in environment
    llm_provider: Literal["gemini", "openai", "fake"] = Field(
        default_factory=lambda: os.getenv(
            "LLM_PROVIDER",
            "gemini" if os.getenv("GEMINI_API_KEY") else ("openai" if os.getenv("OPENAI_API_KEY") else "fake")
        ).lower()  # type: ignore
    )
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Timeouts & budgets (seconds)
    request_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "28.0"))
    )
    llm_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "8.0"))
    )
    llm_max_retries: int = Field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "1"))
    )
    solver_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("SOLVER_TIMEOUT_SECONDS", "5.0"))
    )

    # Logging
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Testing flag for live provider calls
    run_live_llm_tests: bool = Field(
        default_factory=lambda: os.getenv("RUN_LIVE_LLM_TESTS", "0").lower() in ("1", "true", "yes")
    )


settings = Settings()
