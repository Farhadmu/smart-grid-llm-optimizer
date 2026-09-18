"""Deterministic guardrail validation for LLM directive interpretations."""

import math
from typing import Any, Dict, List, Optional
from app.models.schemas import DirectiveInterpretationItem, DirectiveType

VALID_DIRECTIVE_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


class GuardrailValidationError(ValueError):
    """Raised when an LLM directive interpretation violates deterministic guardrails."""
    pass


def validate_directive_interpretations(
    raw_items: List[Dict[str, Any]],
    expected_count: int,
    battery_capacity_kwh: float,
) -> List[DirectiveInterpretationItem]:
    """
    Deterministically validate and normalize structured LLM interpretations.

    Checks:
    1. Exact count matches input notes.
    2. Note-index bijection and order (0..N-1).
    3. Directive type is one of the 6 allowed enums.
    4. `applies` boolean semantics (False iff no_op).
    5. Structured adjustment shape and exact keys per directive.
    6. Hours list validity (unique, 0..23, non-empty, sorted ascending).
    7. Factor range [0.0, 1.0] for solar_reduction.
    8. Minimum reserve [0.0, capacity_kwh] for minimum_battery_reserve.
    9. Max grid cap >= 0.0 for max_grid_window.
    """
    if not isinstance(raw_items, list):
        raise GuardrailValidationError(f"Expected list of interpretations, got {type(raw_items).__name__}")

    if len(raw_items) != expected_count:
        raise GuardrailValidationError(
            f"Interpretation count mismatch: expected {expected_count}, got {len(raw_items)}"
        )

    validated: List[DirectiveInterpretationItem] = []

    for expected_idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise GuardrailValidationError(f"Interpretation item {expected_idx} is not an object")

        # 1. note_index
        note_idx = item.get("note_index")
        if note_idx != expected_idx:
            raise GuardrailValidationError(
                f"Note index out of order or invalid: expected {expected_idx}, got {note_idx}"
            )

        # 2. directive_type
        dtype = item.get("directive_type")
        if dtype not in VALID_DIRECTIVE_TYPES:
            raise GuardrailValidationError(
                f"Item {expected_idx}: unsupported directive_type '{dtype}'"
            )

        # 3. applies boolean
        applies = item.get("applies")
        if not isinstance(applies, bool):
            raise GuardrailValidationError(f"Item {expected_idx}: applies must be boolean")

        if dtype == "no_op" and applies is not False:
            raise GuardrailValidationError(
                f"Item {expected_idx}: applies must be False for 'no_op'"
            )
        if dtype != "no_op" and applies is not True:
            raise GuardrailValidationError(
                f"Item {expected_idx}: applies must be True for active directive '{dtype}'"
            )

        # 4. structured_adjustment shape
        adj = item.get("structured_adjustment")
        explanation = item.get("explanation", "")
        if not isinstance(explanation, str) or not explanation.strip():
            explanation = f"Interpreted directive {dtype}"

        if dtype == "no_op":
            if adj is not None:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: structured_adjustment must be null for 'no_op'"
                )
            validated.append(
                DirectiveInterpretationItem(
                    note_index=note_idx,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=explanation.strip(),
                )
            )
            continue

        if not isinstance(adj, dict):
            raise GuardrailValidationError(
                f"Item {expected_idx}: structured_adjustment must be an object for '{dtype}', got {type(adj).__name__}"
            )

        # 5. Hours validation
        raw_hours = adj.get("hours")
        if not isinstance(raw_hours, list) or len(raw_hours) == 0:
            raise GuardrailValidationError(
                f"Item {expected_idx}: 'hours' must be a non-empty list of integers"
            )

        cleaned_hours: List[int] = []
        for h in raw_hours:
            if isinstance(h, bool) or not isinstance(h, int):
                raise GuardrailValidationError(f"Item {expected_idx}: hour value {h} is not an integer")
            if h < 0 or h > 23:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: hour value {h} out of bounds [0, 23]"
                )
            cleaned_hours.append(h)

        if len(cleaned_hours) != len(set(cleaned_hours)):
            raise GuardrailValidationError(f"Item {expected_idx}: duplicate hours found in {cleaned_hours}")

        sorted_hours = sorted(cleaned_hours)

        # 6. Directive-specific fields
        clean_adj: Dict[str, Any] = {"hours": sorted_hours}

        if dtype == "solar_reduction":
            allowed_keys = {"hours", "factor"}
            if set(adj.keys()) != allowed_keys:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: solar_reduction must contain exactly keys {allowed_keys}, got {set(adj.keys())}"
                )
            factor = adj.get("factor")
            if isinstance(factor, bool) or not isinstance(factor, (int, float)):
                raise GuardrailValidationError(f"Item {expected_idx}: factor must be a number")
            factor = float(factor)
            if not math.isfinite(factor) or factor < 0.0 or factor > 1.0:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: factor must be in range [0.0, 1.0], got {factor}"
                )
            clean_adj["factor"] = factor

        elif dtype == "minimum_battery_reserve":
            allowed_keys = {"hours", "minimum_energy_kwh"}
            if set(adj.keys()) != allowed_keys:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: minimum_battery_reserve must contain exactly keys {allowed_keys}, got {set(adj.keys())}"
                )
            min_energy = adj.get("minimum_energy_kwh")
            if isinstance(min_energy, bool) or not isinstance(min_energy, (int, float)):
                raise GuardrailValidationError(f"Item {expected_idx}: minimum_energy_kwh must be a number")
            min_energy = float(min_energy)
            if not math.isfinite(min_energy) or min_energy < 0.0:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: minimum_energy_kwh must be non-negative, got {min_energy}"
                )
            if min_energy > battery_capacity_kwh:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: minimum_energy_kwh ({min_energy}) exceeds battery capacity ({battery_capacity_kwh})"
                )
            clean_adj["minimum_energy_kwh"] = min_energy

        elif dtype == "no_charge_window":
            allowed_keys = {"hours"}
            if set(adj.keys()) != allowed_keys:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: no_charge_window must contain only 'hours', got {set(adj.keys())}"
                )

        elif dtype == "no_discharge_window":
            allowed_keys = {"hours"}
            if set(adj.keys()) != allowed_keys:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: no_discharge_window must contain only 'hours', got {set(adj.keys())}"
                )

        elif dtype == "max_grid_window":
            allowed_keys = {"hours", "max_grid_kwh"}
            if set(adj.keys()) != allowed_keys:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: max_grid_window must contain exactly keys {allowed_keys}, got {set(adj.keys())}"
                )
            max_grid = adj.get("max_grid_kwh")
            if isinstance(max_grid, bool) or not isinstance(max_grid, (int, float)):
                raise GuardrailValidationError(f"Item {expected_idx}: max_grid_kwh must be a number")
            max_grid = float(max_grid)
            if not math.isfinite(max_grid) or max_grid < 0.0:
                raise GuardrailValidationError(
                    f"Item {expected_idx}: max_grid_kwh must be non-negative, got {max_grid}"
                )
            clean_adj["max_grid_kwh"] = max_grid

        validated.append(
            DirectiveInterpretationItem(
                note_index=note_idx,
                applies=True,
                directive_type=dtype,  # type: ignore
                structured_adjustment=clean_adj,
                explanation=explanation.strip(),
            )
        )

    return validated
