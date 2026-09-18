"""Linear programming solver using scipy.optimize.linprog (HiGHS)."""

from typing import List, Optional, Tuple
import numpy as np
from scipy.optimize import linprog

from app.models.internal import CompiledScenario, OptimizationSolution
from app.models.schemas import HourlyPlanItem

EPSILON = 1e-7


class SolverError(Exception):
    """Raised when the optimization problem is infeasible or solver fails."""
    def __init__(self, message: str, code: str = "OPTIMIZATION_FAILED", status: int = -1):
        super().__init__(message)
        self.code = code
        self.status = status


def solve_energy_optimization(compiled: CompiledScenario) -> OptimizationSolution:
    """
    Formulate and solve the 24-hour cost minimization linear program.

    Variables vector structure (96 decision variables):
    - G[0..23]: Grid import (indices 0..23)
    - U[0..23]: Solar used (indices 24..47)
    - X[0..23]: Signed battery flow (+ charge, - discharge) (indices 48..71)
    - E[0..23]: Battery energy after hour h (indices 72..95)
    """
    N = 24
    num_vars = 4 * N

    # Objective coefficients: minimize sum(G[h] * T[h])
    c = np.zeros(num_vars, dtype=np.float64)
    c[0:N] = compiled.tariff

    # Variable bounds
    bounds: List[Tuple[Optional[float], Optional[float]]] = []

    # 1. G[h] >= 0, G[h] <= grid_cap[h]
    for h in range(N):
        cap = compiled.grid_cap[h]
        ub = cap if np.isfinite(cap) else None
        bounds.append((0.0, ub))

    # 2. 0 <= U[h] <= effective_solar[h]
    for h in range(N):
        bounds.append((0.0, float(compiled.effective_solar[h])))

    # 3. Signed battery flow: -R_d <= X[h] <= R_c
    for h in range(N):
        lb = -compiled.max_discharge_rate if compiled.discharge_allowed[h] else 0.0
        ub = compiled.max_charge_rate if compiled.charge_allowed[h] else 0.0
        bounds.append((float(lb), float(ub)))

    # 4. Active battery energy: E_min[h] <= E[h] <= Capacity
    for h in range(N):
        bounds.append((float(compiled.active_min_energy[h]), float(compiled.capacity)))

    # Equalities:
    # 1. Demand balance: G[h] + U[h] - X[h] = D[h]  (24 constraints)
    # 2. Battery state: E[0] - X[0] = E_init; E[h] - E[h-1] - X[h] = 0 (24 constraints)
    # 3. End-of-day neutrality: E[23] = E_init (1 constraint)
    # Total equality constraints: 49
    num_eq = 2 * N + 1
    A_eq = np.zeros((num_eq, num_vars), dtype=np.float64)
    b_eq = np.zeros(num_eq, dtype=np.float64)

    eq_idx = 0

    # Demand balance
    for h in range(N):
        A_eq[eq_idx, h] = 1.0       # G[h]
        A_eq[eq_idx, N + h] = 1.0   # U[h]
        A_eq[eq_idx, 2 * N + h] = -1.0  # -X[h]
        b_eq[eq_idx] = float(compiled.demand[h])
        eq_idx += 1

    # Battery transitions
    for h in range(N):
        A_eq[eq_idx, 3 * N + h] = 1.0      # E[h]
        A_eq[eq_idx, 2 * N + h] = -1.0     # -X[h]
        if h == 0:
            b_eq[eq_idx] = float(compiled.initial_energy)
        else:
            A_eq[eq_idx, 3 * N + h - 1] = -1.0  # -E[h-1]
            b_eq[eq_idx] = 0.0
        eq_idx += 1

    # End-of-day neutrality
    A_eq[eq_idx, 3 * N + 23] = 1.0  # E[23]
    b_eq[eq_idx] = float(compiled.initial_energy)
    eq_idx += 1

    # Solve using HiGHS with explicit time limit
    res = linprog(
        c,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options={"presolve": True, "time_limit": float(compiled.solver_timeout_seconds)},
    )

    if not res.success:
        if "time limit" in res.message.lower():
            err_code = "OPTIMIZATION_TIMEOUT"
        else:
            status_code_map = {
                1: "OPTIMIZATION_ITERATION_LIMIT",
                2: "OPTIMIZATION_INFEASIBLE",
                3: "OPTIMIZATION_UNBOUNDED",
                4: "OPTIMIZATION_NUMERICAL_DIFFICULTY",
                5: "OPTIMIZATION_TIMEOUT",
            }
            err_code = status_code_map.get(res.status, "OPTIMIZATION_FAILED")
        raise SolverError(
            f"LP Solver failed: {res.message} (status {res.status})",
            code=err_code,
            status=res.status,
        )


    x = res.x
    grid = x[0:N]
    solar_used = x[N : 2 * N]
    battery_flow = x[2 * N : 3 * N]
    battery_energy = x[3 * N : 4 * N]

    return OptimizationSolution(
        success=True,
        status_message=res.message,
        grid=grid,
        solar_used=solar_used,
        battery_flow=battery_flow,
        battery_energy=battery_energy,
        total_cost=float(res.fun),
    )


def map_solution_to_hourly_plan(solution: OptimizationSolution) -> List[HourlyPlanItem]:
    """
    Map decision variables into canonical HourlyPlanItems with action and magnitude.
    Enforces that idle hours have battery_kwh = 0.0 and normalizes -0.0.
    """
    N = 24
    plan: List[HourlyPlanItem] = []

    for h in range(N):
        g = float(solution.grid[h])
        u = float(solution.solar_used[h])
        flow = float(solution.battery_flow[h])
        energy = float(solution.battery_energy[h])

        # Normalize small numerical artifacts
        if abs(g) < EPSILON:
            g = 0.0
        if abs(u) < EPSILON:
            u = 0.0

        if flow > EPSILON:
            action = "charge"
            battery_kwh = flow
        elif flow < -EPSILON:
            action = "discharge"
            battery_kwh = -flow
        else:
            action = "idle"
            battery_kwh = 0.0

        # Safe rounding to 4 decimal places for stable representation
        plan.append(
            HourlyPlanItem(
                hour=h,
                grid_kwh=round(g, 4),
                solar_used_kwh=round(u, 4),
                battery_action=action,  # type: ignore
                battery_kwh=round(battery_kwh, 4),
                battery_energy_after_kwh=round(energy, 4),
            )
        )

    return plan
