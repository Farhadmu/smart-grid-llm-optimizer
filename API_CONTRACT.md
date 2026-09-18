# ⚡ GridWise LLM — API Contract & Schema Specification

> **Official Service Contract, OpenAPI Specification, and Protocol Documentation**  
> System: GridWise Campus Microgrid Energy Optimization Service  
> Version: `1.0.0` | Protocols: `HTTP/1.1`, `HTTP/2` | Content-Type: `application/json`

---

## 📌 Table of Contents
1. [Architectural Boundary & Overview](#1-architectural-boundary--overview)
2. [Service Endpoints](#2-service-endpoints)
3. [Client HTTP Headers & Diagnostic Overrides](#3-client-http-headers--diagnostic-overrides)
4. [Endpoint: `GET /health`](#4-endpoint-get-health)
5. [Endpoint: `POST /optimize-energy`](#5-endpoint-post-optimize-energy)
   - [5.1 Request Contract & Validation Rules](#51-request-contract--validation-rules)
   - [5.2 Annotated Request Example](#52-annotated-request-example)
   - [5.3 Response Contract & Field Definitions](#53-response-contract--field-definitions)
   - [5.4 Annotated Response Example](#54-annotated-response-example)
6. [Mathematical Invariants Enforced by Replay Engine](#6-mathematical-invariants-enforced-by-replay-engine)
7. [Standard Error Envelope & HTTP Status Codes](#7-standard-error-envelope--http-status-codes)
8. [Machine-Readable Schemas Index](#8-machine-readable-schemas-index)

---

## 1. Architectural Boundary & Overview

GridWise optimizes 24-hour campus microgrid energy dispatch under time-varying electricity tariffs, rooftop solar generation, and battery storage constraints, while translating free-form operator instructions into mathematical linear programming (LP) bounds.

```text
HTTP Client (Dashboard / Evaluation Runner / curl)
                     │
                     │ POST /optimize-energy (application/json)
                     ▼
┌────────────────────────────────────────────────────────┐
│                   GridWise Service                     │
│                                                        │
│  1. Strict Pydantic Schema Validation (HTTP 400 / 422) │
│  2. LLM Directive Interpretation (Strict JSON Schema)  │
│  3. Deterministic Guardrail Validation                 │
│  4. Linear Program Matrix Compilation                  │
│  5. HiGHS LP Solver (Continuous Primal Simplex)        │
│  6. Independent 12-Invariant Replay Validation         │
└────────────────────────────────────────────────────────┘
                     │
                     ▼
       Verified 24-Hour Dispatch Plan (HTTP 200 OK)
```

### Base URLs
- **Live Deployment:** `https://smart-grid-llm-optimizer.onrender.com`
- **Local Development:** `http://127.0.0.1:8000`

---

## 2. Service Endpoints

| Method | Path | Purpose | Required Auth / Evaluation Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Service readiness probe | None. Judged readiness check (`{"status":"ok"}`). |
| `POST` | `/optimize-energy` | 24-hour scenario optimization | None. Judged core API endpoint. |

---

## 3. Client HTTP Headers & Diagnostic Overrides

The API accepts standard JSON requests. Clients can optionally pass custom provider diagnostic headers to evaluate different inference backends:

| Header Name | Type | Example Values | Description |
| :--- | :--- | :--- | :--- |
| `Content-Type` | String | `application/json` | **Required.** Payload serialization format. |
| `X-LLM-Provider` | String | `gemini`, `fake`, `openai` | Optional runtime provider override. |
| `X-Gemini-API-Key` | String | `AIzaSy...` | Optional user-supplied Gemini API key. |
| `X-Gemini-Model` | String | `gemini-2.5-flash` | Gemini model (strictly locked to `gemini-2.5-flash`). |
| `X-OpenAI-API-Key` | String | `sk-...` | Optional user-supplied OpenAI / compatible API key. |
| `X-OpenAI-Model` | String | `gpt-4o-mini`, `gpt-4o` | Optional OpenAI-compatible model identifier. |
| `X-OpenAI-Base-URL` | String | `https://api.openai.com/v1` | Optional gateway (OpenAI, Groq, OpenRouter, Ollama). |

---

## 4. Endpoint: `GET /health`

### Description
A fast, zero-dependency readiness probe. It **must not** invoke external LLM providers or solve optimization problems.

### Response `200 OK`
```json
{
  "status": "ok"
}
```

---

## 5. Endpoint: `POST /optimize-energy`

Accepts a complete 24-hour microgrid scenario and 1 to 3 operator natural-language notes, returning validated directive interpretations and a certified 24-hour hourly dispatch plan.

### 5.1 Request Contract & Validation Rules

```text
OptimizeEnergyRequest
├── scenario_id (string, required, non-empty)
├── operator_notes (array of strings, required, minItems: 1, maxItems: 3)
├── hours (array of HourInput, required, minItems: 24, maxItems: 24)
└── battery (BatteryInput, required)
```

#### Field Specifications:

1. **`scenario_id`** (`string`, required):
   - Non-empty scenario identifier.
   - Echoed verbatim in the response envelope.

2. **`operator_notes`** (`string[]`, required):
   - Exactly 1 to 3 items.
   - Each note must be a non-empty, non-whitespace string containing natural language prose.

3. **`hours`** (`HourInput[]`, required):
   - Array containing **exactly 24 entries**.
   - Hours must cover `0` through `23` with no duplicates and no missing hours.
   - Each `HourInput` object contains:
     - `hour` (`integer`, `0..23`): 0-indexed hour of day.
     - `demand_kwh` (`number`, $\ge 0.0$, finite): Electrical demand.
     - `solar_kwh` (`number`, $\ge 0.0$, finite): Forecasted solar generation.
     - `tariff_bdt_per_kwh` (`number`, $\ge 0.0$, finite): Grid import tariff in BDT/kWh.
   - Note: Numeric values must not be booleans, infinities, or NaN.

4. **`battery`** (`BatteryInput`, required):
   - `capacity_kwh` (`number`, $\ge 0.0$, finite): Maximum storage capacity.
   - `initial_energy_kwh` (`number`, $\ge 0.0$, finite): State of charge at $t=0$.
   - `minimum_energy_kwh` (`number`, $\ge 0.0$, finite): Emergency reserve floor.
   - `max_charge_kwh_per_hour` (`number`, $\ge 0.0$, finite): Max charging rate.
   - `max_discharge_kwh_per_hour` (`number`, $\ge 0.0$, finite): Max discharging rate.
   - **Boundary Invariant:**
     $$0.0 \le \text{minimum\_energy\_kwh} \le \text{initial\_energy\_kwh} \le \text{capacity\_kwh}$$

---

### 5.2 Annotated Request Example

```json
{
  "scenario_id": "CAMPUS-MICROGRID-24H",
  "operator_notes": [
    "Rooftop PV panels will undergo cleaning between 1 PM and 3 PM, reducing generation to roughly 25%.",
    "Keep no less than 60 kWh stored in the battery from 6 PM until 9 PM for the evening campus seminar."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 60.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.5 },
    { "hour": 1, "demand_kwh": 55.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 6.5 },
    { "hour": 2, "demand_kwh": 50.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.5 },
    { "hour": 3, "demand_kwh": 50.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.5 },
    { "hour": 4, "demand_kwh": 52.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.5 },
    { "hour": 5, "demand_kwh": 55.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.5 },
    { "hour": 6, "demand_kwh": 65.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 8.0 },
    { "hour": 7, "demand_kwh": 80.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 8.0 },
    { "hour": 8, "demand_kwh": 110.0, "solar_kwh": 45.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 9, "demand_kwh": 130.0, "solar_kwh": 70.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 10, "demand_kwh": 140.0, "solar_kwh": 90.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 11, "demand_kwh": 145.0, "solar_kwh": 100.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 12, "demand_kwh": 150.0, "solar_kwh": 105.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 13, "demand_kwh": 145.0, "solar_kwh": 100.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 14, "demand_kwh": 140.0, "solar_kwh": 85.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 15, "demand_kwh": 130.0, "solar_kwh": 60.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 16, "demand_kwh": 120.0, "solar_kwh": 35.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 17, "demand_kwh": 135.0, "solar_kwh": 10.0, "tariff_bdt_per_kwh": 15.0 },
    { "hour": 18, "demand_kwh": 150.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0 },
    { "hour": 19, "demand_kwh": 160.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0 },
    { "hour": 20, "demand_kwh": 155.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0 },
    { "hour": 21, "demand_kwh": 140.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 15.0 },
    { "hour": 22, "demand_kwh": 100.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 10.0 },
    { "hour": 23, "demand_kwh": 75.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0 }
  ],
  "battery": {
    "capacity_kwh": 200.0,
    "initial_energy_kwh": 100.0,
    "minimum_energy_kwh": 30.0,
    "max_charge_kwh_per_hour": 50.0,
    "max_discharge_kwh_per_hour": 50.0
  }
}
```

---

### 5.3 Response Contract & Field Definitions

```text
OptimizeEnergyResponse
├── scenario_id (string)
├── directive_interpretation (array of DirectiveInterpretationItem)
├── hourly_plan (array of HourlyPlanItem, length: 24)
├── total_grid_kwh (number)
├── total_cost_bdt (number)
├── peak_grid_kwh (number)
└── plan_summary (string)
```

#### Directive Interpretation Item:
- **`note_index`** (`integer`): 0-indexed reference matching `operator_notes[i]`.
- **`applies`** (`boolean`): `true` for active constraints; `false` only for `no_op`.
- **`directive_type`** (`string`): One of the 6 recognized contract directives:
  1. `solar_reduction`: `structured_adjustment: {"hours": [...], "factor": 0.0..1.0}`
  2. `minimum_battery_reserve`: `structured_adjustment: {"hours": [...], "minimum_energy_kwh": ...}`
  3. `no_charge_window`: `structured_adjustment: {"hours": [...]}`
  4. `no_discharge_window`: `structured_adjustment: {"hours": [...]}`
  5. `max_grid_window`: `structured_adjustment: {"hours": [...], "max_grid_kwh": ...}`
  6. `no_op`: `structured_adjustment: null`
- **`structured_adjustment`** (`object | null`): Machine-enforced parameters.
- **`explanation`** (`string`): Human-readable operational interpretation.

#### Hourly Plan Item:
- **`hour`** (`integer`, `0..23`): Hour index.
- **`grid_kwh`** (`number`): Grid electricity imported during this hour.
- **`solar_used_kwh`** (`number`): Solar electricity consumed locally.
- **`battery_action`** (`string`): Exactly `"charge"`, `"discharge"`, or `"idle"`.
- **`battery_kwh`** (`number`): Flow magnitude ($\ge 0$). Must be `0.0` when `idle`.
- **`battery_energy_after_kwh`** (`number`): Battery stored energy at the end of the hour.

---

### 5.4 Annotated Response Example

```json
{
  "scenario_id": "CAMPUS-MICROGRID-24H",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [13, 14],
        "factor": 0.25
      },
      "explanation": "Solar generation reduced to 25% for hours 13-14 due to panel cleaning."
    },
    {
      "note_index": 1,
      "applies": true,
      "directive_type": "minimum_battery_reserve",
      "structured_adjustment": {
        "hours": [18, 19, 20],
        "minimum_energy_kwh": 60.0
      },
      "explanation": "Enforce minimum battery reserve of 60 kWh from 6 PM to 9 PM."
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 100.0,
      "solar_used_kwh": 0.0,
      "battery_action": "charge",
      "battery_kwh": 40.0,
      "battery_energy_after_kwh": 140.0
    },
    {
      "hour": 1,
      "grid_kwh": 105.0,
      "solar_used_kwh": 0.0,
      "battery_action": "charge",
      "battery_kwh": 50.0,
      "battery_energy_after_kwh": 190.0
    },
    {
      "hour": 23,
      "grid_kwh": 75.0,
      "solar_used_kwh": 0.0,
      "battery_action": "idle",
      "battery_kwh": 0.0,
      "battery_energy_after_kwh": 100.0
    }
  ],
  "total_grid_kwh": 2235.0,
  "total_cost_bdt": 26540.0,
  "peak_grid_kwh": 145.0,
  "plan_summary": "Optimal 24-hour dispatch schedule computed using HiGHS LP solver. Verified deterministic end-of-day neutrality (E[23]=100.0 kWh)."
}
```

---

## 6. Mathematical Invariants Enforced by Replay Engine

Every dispatch schedule emitted by the API is verified by an independent, post-optimization deterministic replay engine asserting **all 12 invariants**:

1. **Hourly Energy Balance**:
   $$\forall t \in \{0..23\}: \quad \text{demand}_t = \text{solar\_used}_t + \text{grid}_t + B_t^{\text{dis}} - B_t^{\text{chg}}$$
2. **Solar Availability & Curtailment**:
   $$0 \le \text{solar\_used}_t \le \text{solar\_effective}_t \le \text{solar}_t$$
3. **Battery State of Charge Dynamics**:
   $$E_t = E_{t-1} + B_t^{\text{chg}} - B_t^{\text{dis}}, \quad \text{with } E_{-1} = \text{initial\_energy\_kwh}$$
4. **Battery Storage Capacity Bound**:
   $$\forall t: \quad E_t \le \text{capacity\_kwh}$$
5. **Battery Reserve Floor**:
   $$\forall t: \quad E_t \ge \max(\text{minimum\_energy\_kwh}, \, \text{directive\_reserve}_t)$$
6. **Maximum Charge Rate**:
   $$\forall t: \quad B_t^{\text{chg}} \le \text{max\_charge\_kwh\_per\_hour}$$
7. **Maximum Discharge Rate**:
   $$\forall t: \quad B_t^{\text{dis}} \le \text{max\_discharge\_kwh\_per\_hour}$$
8. **Action-Magnitude Consistency**:
   $$\text{action}_t = \text{"idle"} \iff \text{battery\_kwh}_t = 0.0$$
   $$\text{action}_t \in \{\text{"charge"}, \text{"discharge"}\} \iff \text{battery\_kwh}_t > 0.0$$
9. **Grid Import Upper Bound**:
   $$\forall t: \quad \text{grid}_t \le \text{grid\_cap}_t$$
10. **Non-Negativity**:
    $$\text{grid}_t \ge 0, \quad \text{solar\_used}_t \ge 0, \quad \text{battery\_kwh}_t \ge 0, \quad E_t \ge 0$$
11. **End-of-Day Neutrality**:
    $$|E_{23} - \text{initial\_energy\_kwh}| \le 10^{-5}$$
12. **Objective Function Cost Optimality**:
    $$\text{total\_cost\_bdt} = \sum_{t=0}^{23} \text{grid}_t \cdot \text{tariff}_t$$

---

## 7. Standard Error Envelope & HTTP Status Codes

The API never returns unformatted server traces or raw provider exceptions. All error responses conform to the standard `ErrorEnvelope`:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable actionable explanation"
  }
}
```

### HTTP Status Code Mapping:

| Status Code | Error Code | Trigger Condition |
| :--- | :--- | :--- |
| `400 Bad Request` | `STRUCTURAL_VALIDATION_ERROR` | Malformed JSON, missing fields, prohibited extra fields, invalid types. |
| `422 Unprocessable Entity` | `SEMANTIC_VALIDATION_ERROR` | Battery initial energy below reserve, missing/duplicate hours, negative numbers. |
| `500 Internal Server Error` | `MODEL_INTERPRETATION_ERROR` | LLM failed schema generation, provider rate limit, or invalid output format. |
| `500 Internal Server Error` | `OPTIMIZATION_TIMEOUT` | Solver exceeded runtime budget (`solver_timeout_seconds`). |
| `500 Internal Server Error` | `OPTIMIZATION_INFEASIBLE` | Contradictory constraints make meeting demand mathematically impossible. |
| `500 Internal Server Error` | `REPLAY_VALIDATION_ERROR` | Generated schedule violated any of the 12 replay invariants. |

---

## 8. Machine-Readable Schemas Index

The repository includes standalone, machine-readable JSON Schema files ready for IDE auto-complete, client generation, or CI contract testing:

| Schema File | Specification Standard | Purpose |
| :--- | :--- | :--- |
| [`schemas/openapi.json`](schemas/openapi.json) | OpenAPI `3.1.0` | Complete service contract including all endpoints, operations, and schemas. |
| [`schemas/optimize_energy_request.json`](schemas/optimize_energy_request.json) | JSON Schema `Draft 2020-12` | Schema for `POST /optimize-energy` request body. |
| [`schemas/optimize_energy_response.json`](schemas/optimize_energy_response.json) | JSON Schema `Draft 2020-12` | Schema for `POST /optimize-energy` successful response. |
| [`schemas/error_envelope.json`](schemas/error_envelope.json) | JSON Schema `Draft 2020-12` | Schema for standardized error responses (`400`, `422`, `500`). |
| [`schemas/health_response.json`](schemas/health_response.json) | JSON Schema `Draft 2020-12` | Schema for `GET /health` response. |

To regenerate or verify all schemas from code:
```bash
python3 scripts/export_schemas.py
```
