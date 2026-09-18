"""Deterministic fake LLM interpreter for unit tests, edge-case testing, and CI."""

import re
from typing import Any, Dict, List, Optional
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import validate_directive_interpretations
from app.models.schemas import DirectiveInterpretationItem


def _parse_time_window(text: str) -> Optional[List[int]]:
    """Parse common 12-hour / 24-hour time ranges into start-inclusive, end-exclusive hours."""
    t_lower = text.lower()

    # Pattern: X (am/pm/noon) to/until/and Y (am/pm/noon)
    # Examples:
    # "noon until 2 pm", "1 pm to 3 pm", "2 am until 5 am", "10 am until noon",
    # "11 am and 2 pm", "11 am until 1 pm", "5 pm until 7 pm", "6 pm until 9 pm",
    # "6 pm until 10 pm", "7 pm until 9 pm", "7 pm until 10 pm"

    def time_to_hour(s: str) -> Optional[int]:
        s = s.strip()
        if s in ("noon", "12 noon", "12 pm"):
            return 12
        if s in ("midnight", "12 am"):
            return 0
        m = re.match(r"(\d+)(?::(\d+))?\s*(am|pm)?", s)
        if not m:
            return None
        hr = int(m.group(1))
        meridiem = m.group(3)
        if meridiem == "pm" and hr < 12:
            hr += 12
        elif meridiem == "am" and hr == 12:
            hr = 0
        return hr

    # match "from A (am/pm/noon) until/to/and B (am/pm/noon)" or "between A ... and B ..."
    pattern = r"(?:from|between)?\s*(\d+(?::\d+)?\s*(?:am|pm)?|noon|midnight)\s*(?:until|to|-|and)\s*(\d+(?::\d+)?\s*(?:am|pm)?|noon|midnight)"
    match = re.search(pattern, t_lower)
    if match:
        start_str = match.group(1)
        end_str = match.group(2)
        # If start didn't have am/pm, inherit from end if sensible
        if "am" not in start_str and "pm" not in start_str and start_str not in ("noon", "midnight"):
            if "pm" in end_str:
                start_str += " pm"
            elif "am" in end_str:
                start_str += " am"

        h_start = time_to_hour(start_str)
        h_end = time_to_hour(end_str)

        if h_start is not None and h_end is not None:
            if h_start < h_end:
                return list(range(h_start, h_end))
            elif h_start > h_end:  # Crossing midnight
                return sorted(list(range(h_start, 24)) + list(range(0, h_end)))
            else:
                return [h_start]

    return None


class FakeInterpreter(LLMInterpreter):
    """
    Deterministic fake interpreter for offline testing.
    Can be configured to fail, produce corrupt data, or parse notes using rule patterns.
    """

    def __init__(
        self,
        fail_times: int = 0,
        corrupt_times: int = 0,
        canned_responses: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        self.fail_times = fail_times
        self.corrupt_times = corrupt_times
        self.canned_responses = canned_responses or {}
        self.call_count = 0

    async def interpret_notes(
        self,
        notes: List[str],
        battery_capacity_kwh: float,
        scenario_id: str,
        correlation_id: str = "",
        feedback_error: Optional[str] = None,
    ) -> List[DirectiveInterpretationItem]:
        self.call_count += 1

        if self.fail_times > 0:
            self.fail_times -= 1
            raise LLMInterpretationError("Simulated LLM network/provider failure")

        if self.corrupt_times > 0:
            self.corrupt_times -= 1
            # Return corrupt item violating guardrails
            return [
                DirectiveInterpretationItem(
                    note_index=999,
                    applies=True,
                    directive_type="solar_reduction",
                    structured_adjustment={"hours": [-1, 25], "factor": 1.5},
                    explanation="Corrupt test item",
                )
            ]

        # Check canned responses by scenario_id
        if scenario_id in self.canned_responses:
            raw = self.canned_responses[scenario_id]
            return validate_directive_interpretations(raw, len(notes), battery_capacity_kwh)

        # Parse dynamically using linguistic patterns
        raw_items: List[Dict[str, Any]] = []
        for idx, note in enumerate(notes):
            n_lower = note.lower()

            # 1. Distractor / no_op
            is_noop = any(
                phrase in n_lower
                for phrase in [
                    "sports office",
                    "registration deadline",
                    "book-return",
                    "library",
                    "club notices",
                    "student affairs",
                    "seminar room",
                    "booking was moved",
                    "academic calendar",
                    "administrative",
                    "meeting",
                    "cafeteria",
                    "lunch",
                ]
            )

            # 2. Solar reduction
            is_solar = any(
                w in n_lower for w in ["solar", "panel", "cloud", "cleaning", "wash", "inverter"]
            ) and not is_noop

            # 3. Battery reserve
            is_reserve = any(
                w in n_lower
                for w in [
                    "keep at least",
                    "remain in the battery",
                    "stored in the battery",
                    "reserve",
                    "data center requires",
                ]
            ) and not is_noop

            # 4. No charge window
            is_no_charge = (
                any(
                    w in n_lower
                    for w in [
                        "charger will be isolated",
                        "charging circuit will be unavailable",
                        "battery charging is disabled",
                        "do not charge",
                        "no charge",
                    ]
                )
                and not is_noop
            )

            # 5. No discharge window
            is_no_discharge = (
                any(
                    w in n_lower
                    for w in [
                        "must not discharge",
                        "do not discharge",
                        "discharge is disabled",
                        "no discharge",
                    ]
                )
                and not is_noop
            )

            # 6. Max grid window
            is_grid_cap = (
                any(
                    w in n_lower
                    for w in [
                        "must not exceed",
                        "never draw more than",
                        "transformer limit",
                        "stay at or below",
                        "grid intake",
                        "grid import must",
                        "feeder is operating under",
                    ]
                )
                and not is_noop
            )


            hours = _parse_time_window(note) or [12, 13]

            if is_solar:
                # Determine factor
                factor = 0.5  # default
                if "80% reduction" in n_lower or "reduced by 80%" in n_lower:
                    factor = 0.20
                elif "25%" in n_lower:
                    factor = 0.25
                elif "half" in n_lower or "50%" in n_lower:
                    factor = 0.50
                elif "one-fifth" in n_lower or "20%" in n_lower:
                    factor = 0.20
                else:
                    m = re.search(r"(\d+)%", n_lower)
                    if m:
                        pct = float(m.group(1))
                        if "reduction" in n_lower or "reduced by" in n_lower:
                            factor = round(1.0 - pct / 100.0, 4)
                        else:
                            factor = round(pct / 100.0, 4)

                raw_items.append({
                    "note_index": idx,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {"hours": hours, "factor": factor},
                    "explanation": f"Solar output adjusted to factor {factor} during specified hours.",
                })

            elif is_no_charge:
                raw_items.append({
                    "note_index": idx,
                    "applies": True,
                    "directive_type": "no_charge_window",
                    "structured_adjustment": {"hours": hours},
                    "explanation": "Battery charging disabled during window.",
                })

            elif is_no_discharge:
                raw_items.append({
                    "note_index": idx,
                    "applies": True,
                    "directive_type": "no_discharge_window",
                    "structured_adjustment": {"hours": hours},
                    "explanation": "Battery discharging disabled during window.",
                })

            elif is_reserve:
                # Check kWh or %
                min_kwh = 100.0
                m_pct = re.search(r"(\d+)%\s*of\s*(?:the\s*)?battery\s*capacity", n_lower)
                if m_pct:
                    fraction = float(m_pct.group(1)) / 100.0
                    min_kwh = round(fraction * battery_capacity_kwh, 2)
                else:
                    m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", n_lower)
                    if m_kwh:
                        min_kwh = float(m_kwh.group(1))

                raw_items.append({
                    "note_index": idx,
                    "applies": True,
                    "directive_type": "minimum_battery_reserve",
                    "structured_adjustment": {
                        "hours": hours,
                        "minimum_energy_kwh": min_kwh,
                    },
                    "explanation": f"Minimum battery reserve set to {min_kwh} kWh during window.",
                })

            elif is_grid_cap:
                cap_kwh = 155.0
                m_cap = re.search(r"(\d+(?:\.\d+)?)\s*kwh", n_lower)
                if m_cap:
                    cap_kwh = float(m_cap.group(1))

                raw_items.append({
                    "note_index": idx,
                    "applies": True,
                    "directive_type": "max_grid_window",
                    "structured_adjustment": {"hours": hours, "max_grid_kwh": cap_kwh},
                    "explanation": f"Grid import capped at {cap_kwh} kWh during window.",
                })

            else:
                # no_op
                raw_items.append({
                    "note_index": idx,
                    "applies": False,
                    "directive_type": "no_op",
                    "structured_adjustment": None,
                    "explanation": "Note does not affect 24-hour energy schedule.",
                })

        return validate_directive_interpretations(raw_items, len(notes), battery_capacity_kwh)
