"""Abstract interface for LLM directive interpretation."""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.schemas import DirectiveInterpretationItem


class LLMInterpretationError(Exception):
    """Exception raised when LLM interpretation fails or produces unparseable output."""
    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


class LLMInterpreter(ABC):
    """Abstract interface that all LLM providers (real or fake) must implement."""

    @abstractmethod
    async def interpret_notes(
        self,
        notes: List[str],
        battery_capacity_kwh: float,
        scenario_id: str,
        correlation_id: str = "",
        feedback_error: Optional[str] = None,
    ) -> List[DirectiveInterpretationItem]:
        """
        Interpret operator notes into structured directive interpretation entries.

        Args:
            notes: List of 1-3 natural language operator notes.
            battery_capacity_kwh: Battery capacity in kWh (needed for percentage reserve conversions).
            scenario_id: Scenario identifier for logging and context.
            correlation_id: Correlation ID for tracing.
            feedback_error: If this is a bounded retry, the deterministic validation error to correct.

        Returns:
            List of DirectiveInterpretationItem, exactly one per note in note_index order.
        """
        pass
