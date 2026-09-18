"""Prompt construction and JSON schema definitions for LLM directive interpretation."""

import json
from typing import Any, Dict, List, Optional

SYSTEM_INSTRUCTION = """You are the expert GridWise energy operator directive parser for campus energy management.
Your task is to interpret 1 to 3 natural-language operator notes for a single 24-hour day (hours 0 to 23) and return a structured JSON array with exactly one interpretation per note, in note_index order.

### ALLOWED DIRECTIVE TYPES (EXACT ENUM STRINGS ONLY)
1. "solar_reduction": Usable rooftop solar is curtailed during specified hours.
   - structured_adjustment: {"hours": [int, ...], "factor": float}
   - "factor" is the USABLE FRACTION REMAINING (0.0 to 1.0), NOT the reduction percentage!
     * "80% reduction" or "reduced by 80%" -> factor is 0.20.
     * "reduced to 25%" or "roughly 25% of forecast" -> factor is 0.25.
     * "about half of the forecast" -> factor is 0.50.
2. "minimum_battery_reserve": Battery stored energy at the end of each specified hour must be at or above this kWh level.
   - structured_adjustment: {"hours": [int, ...], "minimum_energy_kwh": float}
   - If stated in percentage (e.g. "at least 50% of battery capacity"), multiply the fraction by the provided scenario battery capacity in kWh! (e.g. 50% of 200 kWh = 100.0).
3. "no_charge_window": Battery charging is completely forbidden during specified hours.
   - structured_adjustment: {"hours": [int, ...]}
4. "no_discharge_window": Battery discharging is completely forbidden during specified hours.
   - structured_adjustment: {"hours": [int, ...]}
5. "max_grid_window": Grid import must not exceed this cap in each specified hour.
   - structured_adjustment: {"hours": [int, ...], "max_grid_kwh": float}
6. "no_op": Note does NOT affect today's 24-hour campus energy schedule (e.g. sports office deadline, book returns next week, club notices, room reservations, general announcements).
   - structured_adjustment: null
   - applies: false

### RULES & CONSTRAINTS
- Return a JSON object with key "directive_interpretation" containing a list of objects.
- Each object must have:
  * "note_index": integer matching the note's zero-based index (0, 1, 2, ...).
  * "applies": boolean (false ONLY for "no_op", true for all other 5 directive types).
  * "directive_type": one of the 6 allowed directive type strings.
  * "structured_adjustment": object with exact keys above, or null for "no_op".
  * "explanation": concise 1-sentence explanation of what was interpreted.
- Time windows are START-INCLUSIVE and END-EXCLUSIVE:
  * "noon until 2 PM" -> hours [12, 13]
  * "1 PM to 3 PM" -> hours [13, 14]
  * "2 AM until 5 AM" -> hours [2, 3, 4]
  * "10 AM until noon" -> hours [10, 11]
  * "11 AM until 1 PM" -> hours [11, 12]
  * "11 AM and 2 PM" -> hours [11, 12, 13]
  * "2 PM until 4 PM" -> hours [14, 15]
  * "5 PM until 7 PM" -> hours [17, 18]
  * "6 PM until 8 PM" -> hours [18, 19]
  * "6 PM until 9 PM" -> hours [18, 19, 20]
  * "6 PM until 10 PM" -> hours [18, 19, 20, 21]
  * "7 PM until 9 PM" -> hours [19, 20]
  * "7 PM until 10 PM" -> hours [19, 20, 21]
- The "hours" list in structured_adjustment must be sorted ascending with unique integers in 0..23.
- Output pure JSON only. Do not wrap in markdown quotes if possible, or use standard json formatting.
"""

DIRECTIVE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "directive_interpretation": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "note_index": {"type": "integer"},
                    "applies": {"type": "boolean"},
                    "directive_type": {
                        "type": "string",
                        "enum": [
                            "solar_reduction",
                            "minimum_battery_reserve",
                            "no_charge_window",
                            "no_discharge_window",
                            "max_grid_window",
                            "no_op",
                        ],
                    },
                    "structured_adjustment": {
                        "type": ["object", "null"],
                        "properties": {
                            "hours": {"type": "array", "items": {"type": "integer"}},
                            "factor": {"type": "number"},
                            "minimum_energy_kwh": {"type": "number"},
                            "max_grid_kwh": {"type": "number"},
                        },
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["note_index", "applies", "directive_type", "explanation"],
            },
        }
    },
    "required": ["directive_interpretation"],
}


def build_user_prompt(
    notes: List[str],
    battery_capacity_kwh: float,
    feedback_error: Optional[str] = None,
) -> str:
    """Construct the user prompt for interpreting notes."""
    prompt_lines = [
        f"Scenario Battery Capacity: {battery_capacity_kwh} kWh",
        "Operator notes to interpret in order:",
    ]
    for idx, note in enumerate(notes):
        prompt_lines.append(f"Note [{idx}]: \"{note}\"")

    if feedback_error:
        prompt_lines.append(
            f"\nIMPORTANT CORRECTION: Your previous output failed deterministic validation:\n{feedback_error}\n"
            "Please fix the error and output valid JSON according to all rules."
        )

    return "\n".join(prompt_lines)
