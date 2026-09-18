"""Full pipeline orchestrator coordinating LLM interpretation, compilation, optimization, and replay."""

import asyncio
import time
import uuid
from typing import List, Optional
from app.config import Settings
from app.llm.interface import LLMInterpreter, LLMInterpretationError
from app.llm.guardrails import GuardrailValidationError
from app.models.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    DirectiveInterpretationItem,
)
from app.optimizer.compiler import compile_scenario_and_directives
from app.optimizer.solver import solve_energy_optimization, map_solution_to_hourly_plan, SolverError
from app.replay.validator import replay_and_recalculate_plan, ReplayValidationError
from app.logging_utils import logger


class OrchestrationError(Exception):
    """Controlled error raised during request processing."""
    def __init__(self, code: str, message: str, status_code: int = 500):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


async def process_energy_optimization(
    request: OptimizeEnergyRequest,
    interpreter: LLMInterpreter,
    settings: Settings,
    correlation_id: Optional[str] = None,
) -> OptimizeEnergyResponse:
    """
    Execute the judged GridWise pipeline:
    1. Validate request (already validated by Pydantic before this function).
    2. LLM directive interpretation with bounded 1-retry on guardrail failure.
    3. Compile directives with conservative intersection policy.
    4. Solve 24-hour cost minimization linear program.
    5. Clean up numbers and map to canonical hourly plan.
    6. Independently replay the emitted plan against energy invariants.
    7. Recalculate totals from emitted plan.
    8. Return exact organizer response schema.
    """
    corr_id = correlation_id or str(uuid.uuid4())
    scenario_id = request.scenario_id
    t_start = time.time()

    logger.info(
        "optimization_request_started",
        correlation_id=corr_id,
        scenario_id=scenario_id,
        notes_count=len(request.operator_notes),
    )

    # 1. LLM Directive Interpretation (with bounded retry)
    t_llm_start = time.time()
    directives: Optional[List[DirectiveInterpretationItem]] = None
    last_error_feedback: Optional[str] = None

    max_attempts = 1 + settings.llm_max_retries
    for attempt in range(1, max_attempts + 1):
        try:
            directives = await interpreter.interpret_notes(
                notes=request.operator_notes,
                battery_capacity_kwh=request.battery.capacity_kwh,
                scenario_id=scenario_id,
                correlation_id=corr_id,
                feedback_error=last_error_feedback,
            )
            break
        except (GuardrailValidationError, LLMInterpretationError) as e:
            logger.warning(
                "llm_interpretation_attempt_failed",
                correlation_id=corr_id,
                scenario_id=scenario_id,
                attempt=attempt,
                error_type=type(e).__name__,
                error_msg=str(e),
            )
            if attempt < max_attempts:
                last_error_feedback = f"Validation failed: {str(e)}"
                continue
            else:
                raise OrchestrationError(
                    code="MODEL_INTERPRETATION_ERROR",
                    message="Failed to obtain valid directive interpretations from LLM",
                    status_code=500,
                )

    if not directives:
        raise OrchestrationError(
            code="MODEL_INTERPRETATION_ERROR",
            message="No directives produced by interpretation subsystem",
            status_code=500,
        )

    t_llm_duration = (time.time() - t_llm_start) * 1000
    logger.info(
        "llm_interpretation_completed",
        correlation_id=corr_id,
        scenario_id=scenario_id,
        duration_ms=t_llm_duration,
        directives_count=len(directives),
    )

    # 2. Compile Scenario & Directives
    compiled = compile_scenario_and_directives(
        scenario_id=scenario_id,
        hours_input=request.hours,
        battery_input=request.battery,
        directives=directives,
        solver_timeout_seconds=settings.solver_timeout_seconds,
    )

    # 3. Solve Linear Program (executed in thread pool with timeout to prevent event loop blocking)
    t_solver_start = time.time()
    try:
        solution = await asyncio.wait_for(
            asyncio.to_thread(solve_energy_optimization, compiled),
            timeout=settings.solver_timeout_seconds + 1.0,
        )
    except asyncio.TimeoutError:
        logger.error(
            "solver_timeout_exceeded",
            correlation_id=corr_id,
            scenario_id=scenario_id,
        )
        raise OrchestrationError(
            code="OPTIMIZATION_TIMEOUT",
            message=f"Energy optimization exceeded solver timeout of {settings.solver_timeout_seconds}s",
            status_code=500,
        )
    except SolverError as e:
        logger.error(
            "solver_failed",
            correlation_id=corr_id,
            scenario_id=scenario_id,
            error=str(e),
            code=e.code,
        )
        raise OrchestrationError(
            code=e.code,
            message=f"Energy schedule optimization failed: {str(e)}",
            status_code=500,
        )
    t_solver_duration = (time.time() - t_solver_start) * 1000

    # 4. Map solution to hourly plan
    hourly_plan = map_solution_to_hourly_plan(solution)

    # 5. Independent Replay Validation & Totals Recalculation
    try:
        total_grid_kwh, total_cost_bdt, peak_grid_kwh = replay_and_recalculate_plan(
            plan=hourly_plan,
            compiled=compiled,
        )
    except ReplayValidationError as e:
        logger.error(
            "replay_validation_failed",
            correlation_id=corr_id,
            scenario_id=scenario_id,
            error=str(e),
        )
        raise OrchestrationError(
            code="REPLAY_VALIDATION_FAILED",
            message=f"Completed schedule failed independent replay verification: {str(e)}",
            status_code=500,
        )

    # 6. Concise explanatory summary
    total_duration_ms = (time.time() - t_start) * 1000
    applied_types = [d.directive_type for d in directives if d.applies]
    summary = (
        f"24-hour cost-optimal schedule computed in {total_duration_ms:.1f}ms. "
        f"Active directives applied: {', '.join(applied_types) if applied_types else 'none'}. "
        f"Total grid import: {total_grid_kwh:.2f} kWh, Total cost: {total_cost_bdt:.2f} BDT, "
        f"Peak grid import: {peak_grid_kwh:.2f} kWh."
    )

    logger.info(
        "optimization_request_succeeded",
        correlation_id=corr_id,
        scenario_id=scenario_id,
        total_duration_ms=total_duration_ms,
        total_cost_bdt=total_cost_bdt,
        total_grid_kwh=total_grid_kwh,
        peak_grid_kwh=peak_grid_kwh,
    )

    return OptimizeEnergyResponse(
        scenario_id=scenario_id,
        directive_interpretation=directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=total_grid_kwh,
        total_cost_bdt=total_cost_bdt,
        peak_grid_kwh=peak_grid_kwh,
        plan_summary=summary,
    )
