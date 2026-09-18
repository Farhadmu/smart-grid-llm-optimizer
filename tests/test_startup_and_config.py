"""Tests for configuration validation, production readiness, and startup checks."""

import unittest
from pydantic import ValidationError
from app.config import Settings, ConfigurationError


class TestStartupAndConfig(unittest.TestCase):
    """Verify production credential enforcement and parameter bounds."""

    def test_fake_provider_prohibited_in_production(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(app_env="production", llm_provider="fake")
        self.assertIn("prohibited in production mode", str(ctx.exception))

    def test_missing_gemini_key_in_production(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(app_env="production", llm_provider="gemini", gemini_api_key="")
        self.assertIn("GEMINI_API_KEY is missing", str(ctx.exception))

    def test_placeholder_gemini_key_in_production(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(
                app_env="production",
                llm_provider="gemini",
                gemini_api_key="YOUR_GEMINI_API_KEY_HERE",
            )
        self.assertIn("placeholder", str(ctx.exception))

    def test_missing_openai_key_in_production(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(app_env="production", llm_provider="openai", openai_api_key="")
        self.assertIn("OPENAI_API_KEY is missing", str(ctx.exception))


    def test_valid_production_credentials(self):
        s1 = Settings(
            app_env="production",
            llm_provider="gemini",
            gemini_api_key="valid-secret-key-123",
        )
        self.assertEqual(s1.gemini_api_key, "valid-secret-key-123")

        s2 = Settings(
            app_env="production",
            llm_provider="openai",
            openai_api_key="sk-valid-secret-key-456",
        )
        self.assertEqual(s2.openai_api_key, "sk-valid-secret-key-456")

    def test_development_mode_allows_fake_provider(self):
        s = Settings(app_env="development", llm_provider="fake")
        self.assertEqual(s.llm_provider, "fake")

    def test_test_mode_allows_fake_provider(self):
        s = Settings(app_env="test", llm_provider="fake")
        self.assertEqual(s.llm_provider, "fake")

    def test_port_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(app_env="test", port=0)
        with self.assertRaises(ValidationError):
            Settings(app_env="test", port=70000)

    def test_negative_timeouts_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(app_env="test", request_timeout_seconds=-1.0)
        with self.assertRaises(ValidationError):
            Settings(app_env="test", llm_timeout_seconds=0.0)
        with self.assertRaises(ValidationError):
            Settings(app_env="test", solver_timeout_seconds=-5.0)

    def test_retry_bounds(self):
        with self.assertRaises(ValidationError):
            Settings(app_env="test", llm_max_retries=-1)
        with self.assertRaises(ValidationError):
            Settings(app_env="test", llm_max_retries=10)


if __name__ == "__main__":
    unittest.main()
