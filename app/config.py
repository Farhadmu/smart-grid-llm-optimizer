"""Configuration settings and validation for GridWise service."""

import os
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ConfigurationError(ValueError):
    """Raised when runtime or production configuration is invalid."""
    pass


PLACEHOLDER_KEYS = {
    "",
    "your_gemini_api_key_here",
    "your_openai_api_key_here",
    "placeholder",
    "none",
    "changeme",
}


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    app_env: Literal["production", "development", "test"] = Field(
        default_factory=lambda: os.getenv("APP_ENV", "development").lower()  # type: ignore
    )

    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # LLM provider settings
    llm_provider: Literal["gemini", "openai", "fake"] = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower()  # type: ignore
    )
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))


    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_strict_schema: bool = Field(
        default_factory=lambda: os.getenv("OPENAI_STRICT_SCHEMA", "1").lower() in ("1", "true", "yes")
    )

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

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if v < 1 or v > 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @field_validator("request_timeout_seconds", "llm_timeout_seconds", "solver_timeout_seconds")
    @classmethod
    def validate_timeouts(cls, v: float, info) -> float:
        if v <= 0.0:
            raise ValueError(f"{info.field_name} must be strictly positive, got {v}")
        return v

    @field_validator("llm_max_retries")
    @classmethod
    def validate_retries(cls, v: int) -> int:
        if v < 0 or v > 5:
            raise ValueError(f"llm_max_retries must be between 0 and 5, got {v}")
        return v

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "Settings":
        """Validate that credentials are non-placeholder when in production."""
        if self.app_env == "production":
            if self.llm_provider == "fake":
                raise ConfigurationError(
                    "Production configuration error: 'fake' LLM provider is prohibited in production mode. "
                    "Configure LLM_PROVIDER=gemini or LLM_PROVIDER=openai with real credentials, "
                    "or set APP_ENV=development for local testing."
                )

            if self.llm_provider == "gemini":
                key = self.gemini_api_key.strip()
                if not key or key.lower() in PLACEHOLDER_KEYS or "your_" in key.lower():
                    raise ConfigurationError(
                        "Production configuration error: GEMINI_API_KEY is missing or contains placeholder value."
                    )

            elif self.llm_provider == "openai":
                key = self.openai_api_key.strip()
                if not key or key.lower() in PLACEHOLDER_KEYS or "your_" in key.lower():
                    raise ConfigurationError(
                        "Production configuration error: OPENAI_API_KEY is missing or contains placeholder value."
                    )

        return self


def get_settings() -> Settings:
    """Factory creating Settings instance with environment defaults."""
    return Settings()


# Default singleton instance (can be reloaded or overridden in tests)
settings = get_settings()
