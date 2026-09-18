"""Pydantic schemas for request, response, and error payloads."""

import math
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _check_finite_number(v: Any, field_name: str) -> float:
    """Validate that a numeric value is not a boolean, is finite, and not NaN."""
    if isinstance(v, bool):
        raise ValueError(f"{field_name} must not be a boolean")
    if not isinstance(v, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    val = float(v)
    if not math.isfinite(val):
        raise ValueError(f"{field_name} must be finite")
    return val


class HourInput(BaseModel):
    """Input specification for a single hour."""
    model_config = ConfigDict(extra="forbid")

    hour: int = Field(..., description="Hour index from 0 through 23")
    demand_kwh: float = Field(..., description="Forecasted electrical demand in kWh")
    solar_kwh: float = Field(..., description="Forecasted rooftop solar generation in kWh")
    tariff_bdt_per_kwh: float = Field(..., description="Grid electricity price in BDT per kWh")

    @field_validator("hour", mode="before")
    @classmethod
    def validate_hour(cls, v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("hour must be an integer (not boolean or float)")
        if v < 0 or v > 23:
            raise ValueError(f"hour must be between 0 and 23 inclusive, got {v}")
        return v

    @field_validator("demand_kwh", "solar_kwh", "tariff_bdt_per_kwh", mode="before")
    @classmethod
    def validate_non_negative_finite(cls, v: Any, info) -> float:
        val = _check_finite_number(v, info.field_name)
        if val < 0.0:
            raise ValueError(f"{info.field_name} must be non-negative, got {val}")
        return val


class BatteryInput(BaseModel):
    """Battery parameter specifications."""
    model_config = ConfigDict(extra="forbid")

    capacity_kwh: float = Field(..., description="Maximum battery storage capacity in kWh")
    initial_energy_kwh: float = Field(..., description="Battery energy at beginning of day in kWh")
    minimum_energy_kwh: float = Field(..., description="Minimum allowed battery reserve in kWh")
    max_charge_kwh_per_hour: float = Field(..., description="Maximum charging rate in kWh/hour")
    max_discharge_kwh_per_hour: float = Field(..., description="Maximum discharging rate in kWh/hour")

    @field_validator(
        "capacity_kwh",
        "initial_energy_kwh",
        "minimum_energy_kwh",
        "max_charge_kwh_per_hour",
        "max_discharge_kwh_per_hour",
        mode="before",
    )
    @classmethod
    def validate_finite(cls, v: Any, info) -> float:
        val = _check_finite_number(v, info.field_name)
        if info.field_name in (
            "capacity_kwh",
            "minimum_energy_kwh",
            "max_charge_kwh_per_hour",
            "max_discharge_kwh_per_hour",
        ):
            if val < 0.0:
                raise ValueError(f"{info.field_name} must be non-negative, got {val}")
        return val

    @model_validator(mode="after")
    def validate_battery_bounds(self) -> "BatteryInput":
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"minimum_energy_kwh ({self.minimum_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot be below minimum_energy_kwh ({self.minimum_energy_kwh})"
            )
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError(
                f"initial_energy_kwh ({self.initial_energy_kwh}) cannot exceed capacity_kwh ({self.capacity_kwh})"
            )
        return self


class OptimizeEnergyRequest(BaseModel):
    """Top-level scenario optimization request."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., description="Scenario identifier")
    operator_notes: List[str] = Field(
        ..., description="List of 1 to 3 natural-language operator notes"
    )
    hours: List[HourInput] = Field(..., description="24 hourly entries for hours 0..23")
    battery: BatteryInput = Field(..., description="Battery specifications")

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("scenario_id must not be empty or whitespace only")
        # Preserve exact scenario_id without trimming to guarantee exact echo
        return v

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list):
            raise ValueError("operator_notes must be a list of strings")
        if len(v) < 1 or len(v) > 3:
            raise ValueError(f"operator_notes count must be between 1 and 3, got {len(v)}")
        cleaned = []
        for i, note in enumerate(v):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(f"operator_notes[{i}] must be a non-empty string")
            cleaned.append(note.strip())
        return cleaned

    @field_validator("hours")
    @classmethod
    def validate_hours_completeness(cls, v: List[HourInput]) -> List[HourInput]:
        if len(v) != 24:
            raise ValueError(f"hours array must contain exactly 24 entries, got {len(v)}")
        seen_hours = set()
        for h in v:
            if h.hour in seen_hours:
                raise ValueError(f"Duplicate hour {h.hour} in hours array")
            seen_hours.add(h.hour)
        if seen_hours != set(range(24)):
            missing = sorted(set(range(24)) - seen_hours)
            raise ValueError(f"Missing hours in hours array: {missing}")
        return v


# Supported directive types
DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]

BatteryAction = Literal["charge", "discharge", "idle"]


class SolarReductionAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: List[int]
    factor: float


class MinimumBatteryReserveAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: List[int]
    minimum_energy_kwh: float


class NoChargeWindowAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: List[int]


class NoDischargeWindowAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: List[int]


class MaxGridWindowAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: List[int]
    max_grid_kwh: float


class DirectiveInterpretationItem(BaseModel):
    """Structured interpretation for a single operator note."""
    model_config = ConfigDict(extra="forbid")

    note_index: int = Field(..., description="Zero-based index of corresponding input note")
    applies: bool = Field(..., description="False only for no_op; true for all active directives")
    directive_type: DirectiveType = Field(..., description="One of the 6 allowed directive types")
    structured_adjustment: Optional[Dict[str, Any]] = Field(
        None, description="Adjustment parameters, or null for no_op"
    )
    explanation: str = Field(..., description="Short explanation of directive interpretation")


class HourlyPlanItem(BaseModel):
    """Optimized operational plan for a single hour."""
    model_config = ConfigDict(extra="forbid")

    hour: int = Field(..., description="Hour index (0-23)")
    grid_kwh: float = Field(..., description="Grid electricity imported in kWh")
    solar_used_kwh: float = Field(..., description="Solar electricity used in kWh")
    battery_action: BatteryAction = Field(..., description="Battery action: charge, discharge, or idle")
    battery_kwh: float = Field(..., description="Magnitude of battery charge/discharge in kWh")
    battery_energy_after_kwh: float = Field(
        ..., description="Battery stored energy at end of hour in kWh"
    )


class OptimizeEnergyResponse(BaseModel):
    """Top-level successful optimization response matching organizer contract exactly."""
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    directive_interpretation: List[DirectiveInterpretationItem]
    hourly_plan: List[HourlyPlanItem]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


class HealthResponse(BaseModel):
    """Health check response."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"


class ErrorDetail(BaseModel):
    """Safe public error details."""
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorEnvelope(BaseModel):
    """Standard controlled error envelope."""
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
