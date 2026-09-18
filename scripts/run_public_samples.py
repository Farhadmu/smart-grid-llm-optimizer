"""Public sample validation script evaluating all ten organizer sample cases."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Tuple

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.llm.fake_provider import FakeInterpreter
from app.models.schemas import OptimizeEnergyRequest
from app.optimizer.compiler import compile_scenario_and_directives
from app.optimizer.solver import solve_energy_optimization, map_solution_to_hourly_plan
from app.replay.validator import replay_and_recalculate_plan, ReplayValidationError
from app.orchestrator import process_energy_optimization

TOLERANCE = 0.01


def check_interpretation_match(actual_list, expected_list) -> Tuple[bool, str]:
    """Compare machine-checkable interpretation fields against organizer ground truth."""
    if len(actual_list) != len(expected_list):
        return False, f"Count mismatch: got {len(actual_list)}, expected {len(expected_list)}"

    for idx, (actual, exp) in enumerate(zip(actual_list, expected_list)):
        if actual.note_index != exp["note_index"]:
            return False, f"Note index mismatch at {idx}: {actual.note_index} != {exp['note_index']}"
        if actual.applies != exp["applies"]:
            return False, f"applies mismatch at {idx}: {actual.applies} != {exp['applies']}"
        if actual.directive_type != exp["directive_type"]:
            return False, f"directive_type mismatch at {idx}: {actual.directive_type} != {exp['directive_type']}"

        if not exp["applies"]:
            if actual.structured_adjustment is not None:
                return False, f"no_op structured_adjustment should be null at {idx}"
            continue

        exp_adj = exp.get("structured_adjustment", {})
        act_adj = actual.structured_adjustment or {}

        # Check hours
        exp_hours = sorted(exp_adj.get("hours", []))
        act_hours = sorted(act_adj.get("hours", []))
        if exp_hours != act_hours:
            return False, f"hours mismatch at {idx}: {act_hours} != {exp_hours}"

        # Check numeric fields
        dtype = exp["directive_type"]
        if dtype == "solar_reduction":
            exp_factor = exp_adj["factor"]
            act_factor = act_adj.get("factor")
            if abs(exp_factor - act_factor) > TOLERANCE:
                return False, f"factor mismatch at {idx}: {act_factor} != {exp_factor}"
        elif dtype == "minimum_battery_reserve":
            exp_reserve = exp_adj["minimum_energy_kwh"]
            act_reserve = act_adj.get("minimum_energy_kwh")
            if abs(exp_reserve - act_reserve) > TOLERANCE:
                return False, f"reserve mismatch at {idx}: {act_reserve} != {exp_reserve}"
        elif dtype == "max_grid_window":
            exp_cap = exp_adj["max_grid_kwh"]
            act_cap = act_adj.get("max_grid_kwh")
            if abs(exp_cap - act_cap) > TOLERANCE:
                return False, f"grid cap mismatch at {idx}: {act_cap} != {exp_cap}"

    return True, "OK"


async def run_all_samples():
    sample_file = ROOT_DIR / "docs" / "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    if not sample_file.exists():
        print(f"Error: Sample cases file not found at {sample_file}")
        sys.exit(1)

    with open(sample_file, "r") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    print(f"\n========================================================")
    print(f"   GridWise Public Sample Pack Acceptance Test (10 Cases)")
    print(f"========================================================\n")

    interpreter = FakeInterpreter()
    all_passed = True
    results = []

    for i, case in enumerate(cases):
        inp_dict = case["input"]
        exp_dict = case["expected_output"]
        scenario_id = inp_dict["scenario_id"]

        try:
            req = OptimizeEnergyRequest(**inp_dict)
            resp = await process_energy_optimization(req, interpreter, settings)

            # 1. Interpretation check
            int_ok, int_msg = check_interpretation_match(
                resp.directive_interpretation,
                exp_dict["directive_interpretation"],
            )

            # 2. Independent Replay Check against ground truth directives
            compiled = compile_scenario_and_directives(
                scenario_id=scenario_id,
                hours_input=req.hours,
                battery_input=req.battery,
                directives=resp.directive_interpretation,
            )
            replayed_grid, replayed_cost, replayed_peak = replay_and_recalculate_plan(
                plan=resp.hourly_plan,
                compiled=compiled,
            )

            # 3. Cost optimality check
            exp_cost = exp_dict["total_cost_bdt"]
            cost_diff = abs(replayed_cost - exp_cost)
            cost_ok = cost_diff <= TOLERANCE

            passed = int_ok and cost_ok
            if not passed:
                all_passed = False

            status_str = "PASS" if passed else "FAIL"
            print(
                f"[{status_str}] {scenario_id} (Case {i+1:02d}): "
                f"Cost={replayed_cost:.2f} BDT (Exp: {exp_cost:.2f}, Diff: {cost_diff:.4f}) | "
                f"Grid={replayed_grid:.1f} kWh | Peak={replayed_peak:.1f} kWh | "
                f"Interpretation: {int_msg}"
            )

            results.append({
                "scenario_id": scenario_id,
                "passed": passed,
                "cost": replayed_cost,
                "expected_cost": exp_cost,
                "diff": cost_diff,
                "interpretation": int_msg,
            })

        except Exception as e:
            all_passed = False
            print(f"[FAIL] {scenario_id} (Case {i+1:02d}): EXCEPTION {type(e).__name__}: {str(e)}")
            results.append({
                "scenario_id": scenario_id,
                "passed": False,
                "error": f"{type(e).__name__}: {str(e)}",
            })

    print(f"\n========================================================")
    if all_passed:
        print(f" RESULT: ALL {len(cases)} PUBLIC CASES PASSED OPTIMALITY & REPLAY!")
    else:
        print(f" RESULT: ONE OR MORE CASES FAILED VERIFICATION.")
    print(f"========================================================\n")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_samples())
