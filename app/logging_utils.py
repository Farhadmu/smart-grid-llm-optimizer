"""Structured logging utility with secret redaction and correlation IDs."""

import json
import logging
import re
import sys
import time
import uuid
from typing import Any, Dict, Optional

# Patterns that might contain sensitive keys or tokens
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|bearer|token|secret|password|authorization)\s*[:=]\s*['\"]?([^'\"\s,;]+)"),
]


def redact_secrets(text: str) -> str:
    """Redact known secret patterns from string."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1=[REDACTED]", text)
    return text


class StructuredLogger:
    """Safe structured logger producing JSON-formatted log lines."""

    def __init__(self, name: str = "gridwise"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log(
        self,
        level: int,
        event: str,
        correlation_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        stage: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        payload: Dict[str, Any] = {
            "timestamp": time.time(),
            "event": event,
            "correlation_id": correlation_id or "",
            "scenario_id": scenario_id or "",
            "stage": stage or "",
        }
        if duration_ms is not None:
            payload["duration_ms"] = round(duration_ms, 2)
        for k, v in kwargs.items():
            if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
                payload[k] = v
            else:
                payload[k] = str(v)

        raw_json = json.dumps(payload, ensure_ascii=False)
        safe_msg = redact_secrets(raw_json)
        self.logger.log(level, safe_msg)

    def info(self, event: str, **kwargs: Any) -> None:
        self.log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self.log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self.log(logging.ERROR, event, **kwargs)


logger = StructuredLogger()
