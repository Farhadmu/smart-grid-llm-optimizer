"""Directive compiler converting validated interpretations into per-hour constraint arrays."""

from typing import List
import numpy as np

from app.models.schemas import DirectiveInterpretationItem, HourInput, BatteryInput
from app.models.internal import CompiledScenario


def compile_scenario_and_directives(
    scenario_id: str,
    hours_input: List[HourInput],
    battery_input: BatteryInput,
    directives: List[DirectiveInterpretationItem],
) -> CompiledScenario:
    """
    Compile base scenario inputs and validated directives into per-hour numerical arrays.

    Implements the conservative intersection policy:
    - Overlapping solar reductions: take minimum factor for that hour.
    - Overlapping battery reserves: take maximum reserve for that hour.
    - Overlapping grid caps: take minimum cap for that hour.
    - Any active no-charge directive disables charging in that hour.
    - Any active no-discharge directive disables discharging in that hour.
    """
    N = 24
    demand = np.zeros(N, dtype=np.float64)
    base_solar = np.zeros(N, dtype=np.float64)
    solar_factor = np.ones(N, dtype=np.float64)
    tariff = np.zeros(N, dtype=np.float64)

    for h in hours_input:
        idx = h.hour
        demand[idx] = h.demand_kwh
        base_solar[idx] = h.solar_kwh
        tariff[idx] = h.tariff_bdt_per_kwh

    active_min_energy = np.full(N, battery_input.minimum_energy_kwh, dtype=np.float64)
    charge_allowed = np.ones(N, dtype=bool)
    discharge_allowed = np.ones(N, dtype=bool)
    grid_cap = np.full(N, np.inf, dtype=np.float64)

    for d in directives:
        if not d.applies:
            continue

        adj = d.structured_adjustment or {}
        hours = adj.get("hours", [])

        if d.directive_type == "solar_reduction":
            factor = float(adj.get("factor", 1.0))
            for h in hours:
                # Conservative intersection: minimum remaining factor
                solar_factor[h] = min(solar_factor[h], factor)

        elif d.directive_type == "minimum_battery_reserve":
            reserve_kwh = float(adj.get("minimum_energy_kwh", battery_input.minimum_energy_kwh))
            for h in hours:
                # Conservative intersection: maximum reserve requirement
                active_min_energy[h] = max(active_min_energy[h], reserve_kwh)

        elif d.directive_type == "no_charge_window":
            for h in hours:
                charge_allowed[h] = False

        elif d.directive_type == "no_discharge_window":
            for h in hours:
                discharge_allowed[h] = False

        elif d.directive_type == "max_grid_window":
            cap_kwh = float(adj.get("max_grid_kwh", np.inf))
            for h in hours:
                # Conservative intersection: minimum cap
                grid_cap[h] = min(grid_cap[h], cap_kwh)

    effective_solar = base_solar * solar_factor

    return CompiledScenario(
        scenario_id=scenario_id,
        demand=demand,
        effective_solar=effective_solar,
        base_solar=base_solar,
        tariff=tariff,
        capacity=battery_input.capacity_kwh,
        initial_energy=battery_input.initial_energy_kwh,
        active_min_energy=active_min_energy,
        charge_allowed=charge_allowed,
        discharge_allowed=discharge_allowed,
        grid_cap=grid_cap,
        max_charge_rate=battery_input.max_charge_kwh_per_hour,
        max_discharge_rate=battery_input.max_discharge_kwh_per_hour,
    )
