"""Internal dataclasses for compiled scenarios and solver structures."""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np


@dataclass
class CompiledScenario:
    """Compiled scenario parameters with combined directives."""

    scenario_id: str
    demand: np.ndarray          # (24,) float
    effective_solar: np.ndarray # (24,) float
    base_solar: np.ndarray      # (24,) float
    tariff: np.ndarray          # (24,) float
    capacity: float
    initial_energy: float
    active_min_energy: np.ndarray # (24,) float
    charge_allowed: np.ndarray    # (24,) bool
    discharge_allowed: np.ndarray # (24,) bool
    grid_cap: np.ndarray          # (24,) float (np.inf where uncapped)
    max_charge_rate: float
    max_discharge_rate: float


@dataclass
class OptimizationSolution:
    """Raw mathematical solution extracted from LP solver."""

    success: bool
    status_message: str
    grid: np.ndarray         # (24,) G[h]
    solar_used: np.ndarray   # (24,) U[h]
    battery_flow: np.ndarray # (24,) X[h] (+ charge, - discharge)
    battery_energy: np.ndarray # (24,) E[h]
    total_cost: float
