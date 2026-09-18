"""Export OpenAPI specification and individual JSON schemas for GridWise API."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.models.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HealthResponse,
    ErrorEnvelope,
)

SCHEMAS_DIR = ROOT_DIR / "schemas"


def export_schemas():
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. OpenAPI 3.1.0 Full Specification
    openapi_spec = app.openapi()
    openapi_path = SCHEMAS_DIR / "openapi.json"
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, indent=2)
    print(f"Exported: {openapi_path.relative_to(ROOT_DIR)}")

    # 2. OptimizeEnergyRequest JSON Schema
    req_schema = OptimizeEnergyRequest.model_json_schema()
    req_path = SCHEMAS_DIR / "optimize_energy_request.json"
    with open(req_path, "w", encoding="utf-8") as f:
        json.dump(req_schema, f, indent=2)
    print(f"Exported: {req_path.relative_to(ROOT_DIR)}")

    # 3. OptimizeEnergyResponse JSON Schema
    resp_schema = OptimizeEnergyResponse.model_json_schema()
    resp_path = SCHEMAS_DIR / "optimize_energy_response.json"
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(resp_schema, f, indent=2)
    print(f"Exported: {resp_path.relative_to(ROOT_DIR)}")

    # 4. ErrorEnvelope JSON Schema
    err_schema = ErrorEnvelope.model_json_schema()
    err_path = SCHEMAS_DIR / "error_envelope.json"
    with open(err_path, "w", encoding="utf-8") as f:
        json.dump(err_schema, f, indent=2)
    print(f"Exported: {err_path.relative_to(ROOT_DIR)}")

    # 5. HealthResponse JSON Schema
    health_schema = HealthResponse.model_json_schema()
    health_path = SCHEMAS_DIR / "health_response.json"
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(health_schema, f, indent=2)
    print(f"Exported: {health_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    export_schemas()
