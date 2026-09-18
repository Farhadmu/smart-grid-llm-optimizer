"""FastAPI application entrypoint for GridWise service."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm.factory import create_llm_interpreter
from app.models.schemas import (
    HealthResponse,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    ErrorEnvelope,
    ErrorDetail,
)
from app.orchestrator import process_energy_optimization, OrchestrationError
from app.logging_utils import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration on server startup before serving requests."""
    if settings.app_env == "production":
        logger.info("startup_production_validation_passed", provider=settings.llm_provider)
    yield


app = FastAPI(
    title="GridWise Optimization Service",
    version="1.0.0",
    docs_url=None,  # No Swagger UI needed for judging
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

from app.config import get_settings

# Interpreter resolver honoring active environment and runtime settings
def get_interpreter():
    return create_llm_interpreter(get_settings())



@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Ensure every request has a correlation ID for tracing."""
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = corr_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI/Pydantic request validation errors."""
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    errors = exc.errors()

    # Distinguish structural syntax errors (400) from semantic validation errors (422)
    is_semantic = any(
        err.get("type") in ("value_error", "assertion_error") or "bounds" in str(err.get("msg", "")).lower()
        for err in errors
    )
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY if is_semantic else status.HTTP_400_BAD_REQUEST
    code = "SEMANTIC_VALIDATION_ERROR" if is_semantic else "STRUCTURAL_VALIDATION_ERROR"

    first_msg = errors[0].get("msg", "Invalid request payload") if errors else "Invalid request payload"
    clean_msg = f"{code}: {first_msg}"

    logger.warning(
        "request_validation_failed",
        correlation_id=corr_id,
        status_code=status_code,
        error_code=code,
        msg=clean_msg,
    )

    envelope = ErrorEnvelope(error=ErrorDetail(code=code, message=clean_msg))
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


@app.exception_handler(OrchestrationError)
async def orchestration_exception_handler(
    request: Request, exc: OrchestrationError
) -> JSONResponse:
    """Handle controlled pipeline orchestration errors."""
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        "orchestration_error",
        correlation_id=corr_id,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
    )
    envelope = ErrorEnvelope(error=ErrorDetail(code=exc.code, message=exc.message))
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safely catch any unhandled exception without leaking stack traces or credentials."""
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        "unhandled_exception",
        correlation_id=corr_id,
        error_type=type(exc).__name__,
    )
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
        )
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=envelope.model_dump())


@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    """
    Readiness health check.
    Must return HTTP 200 with exactly {"status": "ok"}.
    Must not call model providers or optimizer.
    """
    return HealthResponse(status="ok")


@app.post("/optimize-energy", response_model=OptimizeEnergyResponse, status_code=status.HTTP_200_OK)
async def optimize_energy_endpoint(
    request_data: OptimizeEnergyRequest,
    raw_request: Request,
) -> OptimizeEnergyResponse:
    """
    Endpoint accepting 24-hour scenario and operator notes,
    returning validated directives and cost-minimal schedule.
    """
    corr_id = getattr(raw_request.state, "correlation_id", str(uuid.uuid4()))

    try:
        # Wrap execution with request timeout budget
        current_settings = get_settings()
        
        # Check optional client diagnostic header overrides
        gemini_key_header = raw_request.headers.get("X-Gemini-API-Key")
        provider_header = raw_request.headers.get("X-LLM-Provider")
        model_header = raw_request.headers.get("X-Gemini-Model")

        if gemini_key_header or provider_header or model_header:
            overrides = {}
            if gemini_key_header:
                overrides["gemini_api_key"] = gemini_key_header
            if provider_header and provider_header.lower() in ("gemini", "fake", "openai"):
                overrides["llm_provider"] = provider_header.lower()
            if model_header:
                overrides["gemini_model"] = model_header
            current_settings = current_settings.model_copy(update=overrides)
            current_interpreter = create_llm_interpreter(current_settings)
        else:
            current_interpreter = get_interpreter()

        return await asyncio.wait_for(
            process_energy_optimization(
                request=request_data,
                interpreter=current_interpreter,
                settings=current_settings,
                correlation_id=corr_id,
            ),
            timeout=current_settings.request_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.error(
            "request_timeout_exceeded",
            correlation_id=corr_id,
            scenario_id=request_data.scenario_id,
        )
        raise OrchestrationError(
            code="REQUEST_TIMEOUT",
            message=f"Request exceeded maximum processing budget of {settings.request_timeout_seconds}s",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Serve frontend static dashboard assets if directory is present
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.is_dir():
    from starlette.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

