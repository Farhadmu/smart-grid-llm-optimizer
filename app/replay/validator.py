"""Independent chronological replay validator and totals recalculator."""

import math
from typing import Dict, List, Tuple
from app.models.internal import CompiledScenario
from app.models.schemas import HourlyPlanItem

TOLERANCE = 0.01  # Organizer tolerance is 0.01 kWh / 0.01 BDT


class ReplayValidationError(Exception):
    """Raised when the serialized hourly plan violates energy invariants or directives."""
    pass


def replay_and_recalculate_plan(
    plan: List[HourlyPlanItem],
    compiled: CompiledScenario,
) -> Tuple[float, float, float]:
    """
    Independently replay the final emitted hourly plan against physical laws and directives.

    Returns:
        (total_grid_kwh, total_cost_bdt, peak_grid_kwh)
    """
    # 1. Exactly 24 unique plan hours covering 0-23
    if len(plan) != 24:
        raise ReplayValidationError(f"Plan length must be exactly 24, got {len(plan)}")

    hours_seen = set()
    plan_by_hour: Dict[int, HourlyPlanItem] = {}
    for item in plan:
        if item.hour in hours_seen:
            raise ReplayValidationError(f"Duplicate hour {item.hour} in plan")
        hours_seen.add(item.hour)
        plan_by_hour[item.hour] = item

    if hours_seen != set(range(24)):
        raise ReplayValidationError(f"Plan missing hours: {sorted(set(range(24)) - hours_seen)}")

    current_battery_energy = compiled.initial_energy
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for h in range(24):
        item = plan_by_hour[h]

        # 2. All numeric values finite and non-negative
        for val, name in [
            (item.grid_kwh, "grid_kwh"),
            (item.solar_used_kwh, "solar_used_kwh"),
            (item.battery_kwh, "battery_kwh"),
            (item.battery_energy_after_kwh, "battery_energy_after_kwh"),
        ]:
            if not math.isfinite(val) or val < -1e-6:
                raise ReplayValidationError(f"Hour {h}: {name} must be finite and >= 0, got {val}")

        # 3. Action and magnitude consistency
        action = item.battery_action
        if action == "idle":
            if item.battery_kwh > TOLERANCE:
                raise ReplayValidationError(
                    f"Hour {h}: battery_action is 'idle' but battery_kwh is {item.battery_kwh}"
                )
        elif action in ("charge", "discharge"):
            if item.battery_kwh <= 0.0:
                raise ReplayValidationError(
                    f"Hour {h}: battery_action is '{action}' but battery_kwh is {item.battery_kwh}"
                )
        else:
            raise ReplayValidationError(f"Hour {h}: invalid battery_action '{action}'")

        charge_kwh = item.battery_kwh if action == "charge" else 0.0
        discharge_kwh = item.battery_kwh if action == "discharge" else 0.0

        # 4. Battery transition
        if action == "charge":
            expected_energy = current_battery_energy + item.battery_kwh
        elif action == "discharge":
            expected_energy = current_battery_energy - item.battery_kwh
        else:
            expected_energy = current_battery_energy

        if abs(item.battery_energy_after_kwh - expected_energy) > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery transition mismatch. Previous: {current_battery_energy}, "
                f"action: {action} {item.battery_kwh}, expected after: {expected_energy}, "
                f"reported: {item.battery_energy_after_kwh}"
            )

        # 5. Rate limits
        if charge_kwh > compiled.max_charge_rate + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: charging {charge_kwh} exceeds max charge rate {compiled.max_charge_rate}"
            )
        if discharge_kwh > compiled.max_discharge_rate + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: discharging {discharge_kwh} exceeds max discharge rate {compiled.max_discharge_rate}"
            )

        # 6. Capacity & reserve bounds
        min_reserve = compiled.active_min_energy[h]
        if item.battery_energy_after_kwh < min_reserve - TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery energy {item.battery_energy_after_kwh} below active minimum {min_reserve}"
            )
        if item.battery_energy_after_kwh > compiled.capacity + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: battery energy {item.battery_energy_after_kwh} exceeds capacity {compiled.capacity}"
            )

        # 7. Directive constraints: no-charge / no-discharge windows
        if not compiled.charge_allowed[h] and charge_kwh > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: charging is prohibited by no_charge_window directive, but charged {charge_kwh}"
            )
        if not compiled.discharge_allowed[h] and discharge_kwh > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: discharging is prohibited by no_discharge_window directive, but discharged {discharge_kwh}"
            )

        # 8. Solar used bounds
        max_solar = compiled.effective_solar[h]
        if item.solar_used_kwh > max_solar + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: solar_used {item.solar_used_kwh} exceeds effective solar {max_solar}"
            )

        # 9. Grid cap compliance
        cap = compiled.grid_cap[h]
        if math.isfinite(cap) and item.grid_kwh > cap + TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: grid import {item.grid_kwh} exceeds directive grid cap {cap}"
            )

        # 10. Hourly energy balance: grid + solar_used + discharge = demand + charge
        supply = item.grid_kwh + item.solar_used_kwh + discharge_kwh
        demand = float(compiled.demand[h]) + charge_kwh
        if abs(supply - demand) > TOLERANCE:
            raise ReplayValidationError(
                f"Hour {h}: energy balance violation. Supply: {supply} (grid={item.grid_kwh}, "
                f"solar={item.solar_used_kwh}, disch={discharge_kwh}) != Demand: {demand} "
                f"(base={compiled.demand[h]}, charge={charge_kwh})"
            )

        # Advance state
        current_battery_energy = item.battery_energy_after_kwh
        total_grid += item.grid_kwh
        total_cost += item.grid_kwh * float(compiled.tariff[h])
        if item.grid_kwh > peak_grid:
            peak_grid = item.grid_kwh

    # 11. End-of-day battery neutrality
    if abs(current_battery_energy - compiled.initial_energy) > TOLERANCE:
        raise ReplayValidationError(
            f"End-of-day neutrality violation: ending energy {current_battery_energy} != initial {compiled.initial_energy}"
        )

    # 12. Recalculate totals from final emitted plan
    total_grid_rounded = round(total_grid, 4)
    total_cost_rounded = round(total_cost, 4)
    peak_grid_rounded = round(peak_grid, 4)

    return total_grid_rounded, total_cost_rounded, peak_grid_rounded
