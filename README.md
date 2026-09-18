# GridWise: LLM-Assisted Smart Campus Energy Optimizer
**BUP CSE Fest 2026 Hackathon · Online Preliminary Round**

---

## 1. Executive Overview

GridWise is a production-grade, public HTTP energy management service designed for campus microgrids. It interprets natural-language operator directives using a generative language model, converts them into mathematical constraints via deterministic guardrails, and optimizes a 24-hour energy schedule using a linear program solver.

Before any schedule is returned to the caller, an **independent chronological replay validator** verifies every physical energy balance, battery transition, rate limit, and directive constraint, recalculating totals to prevent drift.

### Core Endpoints
| Endpoint | Method | Purpose | Response |
|---|---|---|---|
| `/health` | `GET` | Readiness health probe | `{"status":"ok"}` (HTTP 200) |
| `/optimize-energy` | `POST` | 24-hour scenario optimization | Full schedule & interpretations (HTTP 200) |

---

## 2. Architecture & Processing Flow

```text
               HTTP POST /optimize-energy
                          │
                          ▼
            [ 1. Request Validator ] ────────► 400 / 422 if malformed
                          │
                          ▼
            [ 2. LLM Interpreter ] ◄────────► Real LLM (Gemini/OpenAI) or Fake
                          │
                          ▼
            [ 3. Guardrail Validator ] ─────► Bounded 1-retry on repairable error;
                          │                   500 if unrecoverable
                          ▼
            [ 4. Directive Compiler ] ──────► Per-hour constraint arrays
                          │                   (conservative intersection)
                          ▼
            [ 5. Linear Optimizer ] ────────► Scipy HiGHS solver
                          │                   (signed battery flow)
                          ▼
            [ 6. Numeric Cleanup ] ─────────► Canonical action (charge/discharge/idle)
                          │
                          ▼
            [ 7. Independent Replay ] ──────► Chronological invariant check
                          │
                          ▼
            [ 8. Totals Recalculation ] ────► Recalculate grid_kwh, cost, peak
                          │
                          ▼
            [ 9. Response Formatter ] ──────► HTTP 200 Organizer Success Schema
```

---

## 3. Exact Role of the LLM & Deterministic Guardrails

### 3.1 LLM Role
The language model interprets synthetic operator notes into structured directive objects.
- **What the LLM does:** Translates natural language into one of six exact directive types, extracts start-inclusive/end-exclusive whole-hour intervals, converts percentage reductions into remaining usable factors, and converts capacity percentages into kWh reserves.
- **What the LLM does NOT do:** The LLM never performs mathematical optimization, never computes schedules, and never directly writes solver constraints without guardrail validation.

### 3.2 Supported Directives (Exact Enums)
1. `solar_reduction`: Usable rooftop solar curtailed. `{"hours": [int, ...], "factor": float}` where `factor` is usable fraction remaining ($0.0 \le \text{factor} \le 1.0$). E.g., "80% reduction" $\rightarrow$ factor `0.2`.
2. `minimum_battery_reserve`: Minimum stored battery energy at end of listed hours. `{"hours": [int, ...], "minimum_energy_kwh": float}`. Percentage language is converted relative to scenario battery capacity (e.g., 50% of 200 kWh $\rightarrow$ 100 kWh).
3. `no_charge_window`: Charging disabled during listed hours. `{"hours": [int, ...]}`.
4. `no_discharge_window`: Discharging disabled during listed hours. `{"hours": [int, ...]}`.
5. `max_grid_window`: Feeder import capped per hour. `{"hours": [int, ...], "max_grid_kwh": float}`.
6. `no_op`: Irrelevant note (club notices, deadlines, meetings). `applies = false`, `structured_adjustment = null`.

### 3.3 Deterministic Guardrails
Every LLM response is validated before optimization:
- Exact 1-to-1 bijection between notes and interpretations (`note_index` $0..N-1$).
- `applies` is `False` strictly for `no_op` and `True` for all other 5 directives.
- `structured_adjustment` is null strictly for `no_op` and an object with exact allowed keys for active directives.
- `hours` are unique integers in $[0, 23]$, sorted ascending.
- Factors strictly in $[0.0, 1.0]$.
- Reserves strictly in $[0.0, \text{capacity\_kwh}]$.
- Grid caps strictly non-negative and finite.
- **Bounded Retry:** On validation error, exactly one repair call is made feeding back the safe error. If validation still fails, the service fails closed with a controlled HTTP 500 error; it **never** silently defaults an invalid active directive to `no_op`.

---

## 4. Directive Compiler & Overlap Policy

When multiple notes affect the same resource in the same hour, the compiler applies a conservative intersection policy:
- **Overlapping solar reductions:** Smallest factor is applied ($\text{effective\_solar}[h] = \text{base\_solar}[h] \times \min(f_1, f_2)$).
- **Overlapping battery reserves:** Largest reserve bound is enforced ($\max(R_1, R_2)$).
- **Overlapping grid caps:** Smallest cap is enforced ($\min(C_1, C_2)$).
- **No-charge / no-discharge windows:** Any active directive disables that action. If both apply, battery flow is strictly zero.

---

## 5. Mathematical Optimization Model

The optimization engine is a deterministic Linear Program solved using HiGHS via `scipy.optimize.linprog`.

### Decision Variables (96 variables for $h \in [0, 23]$):
- $G[h] \ge 0$: Grid electricity import (kWh), bounded by `grid_cap[h]` if active.
- $U[h] \ge 0$: Solar generation used (kWh), bounded by $0 \le U[h] \le \text{effective\_solar}[h]$.
- $X[h]$: Signed battery flow (kWh). Positive for charge ($0 \le X[h] \le R_c$), negative for discharge ($-R_d \le X[h] \le 0$).
- $E[h]$: Stored battery energy at end of hour $h$ (kWh), bounded by $\text{active\_min}[h] \le E[h] \le \text{Capacity}$.

### Objective Function:
$$\min \sum_{h=0}^{23} G[h] \cdot T[h]$$
Where $T[h]$ is the grid tariff in BDT/kWh.

### Equality Constraints:
1. **Hourly Demand Balance:** $G[h] + U[h] - X[h] = D[h] \quad \forall h \in [0, 23]$
2. **Battery Dynamics:**
   - $E[0] - X[0] = E_{\text{init}}$
   - $E[h] - E[h-1] - X[h] = 0 \quad \forall h \in [1, 23]$
3. **End-of-Day Neutrality:** $E[23] = E_{\text{init}}$

### Canonical Solution Mapping:
- If $X[h] > 10^{-7}$: `battery_action = "charge"`, `battery_kwh = X[h]`
- If $X[h] < -10^{-7}$: `battery_action = "discharge"`, `battery_kwh = -X[h]`
- Otherwise: `battery_action = "idle"`, `battery_kwh = 0.0`

---

## 6. Independent Replay Validator

The final emitted `hourly_plan` is independently checked by `app/replay/validator.py`:
1. Plan contains exactly 24 unique hours $0..23$.
2. All numeric values are non-negative and finite.
3. Action and magnitude consistency (`idle` requires `battery_kwh == 0.0`).
4. Physical battery transitions: $E_h = E_{h-1} + \text{charge} - \text{discharge}$.
5. Charge/discharge rate limits are respected.
6. Battery energy stays within active minimum reserve and capacity.
7. Directive windows respected (no charging or discharging during prohibited hours).
8. Solar used does not exceed effective solar after curtailment.
9. Grid import does not exceed directive caps.
10. Exact hourly energy balance: $\text{grid} + \text{solar\_used} + \text{discharge} = \text{demand} + \text{charge}$.
11. Ending battery energy equals initial battery energy.
12. Response totals (`total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`) are recalculated directly from the emitted plan to prevent drift.

---

## 7. Local Setup & Running

### 7.1 Prerequisites
- Python 3.11+ (tested on Python 3.11, 3.12, 3.13)
- `pip`

### 7.2 Installation
```bash
# 1. Clone repository
git clone <repository_url>
cd <repository_folder>

# 2. (Optional) Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install locked dependencies
pip install -r requirements.txt
```

### 7.3 Configuration
Copy `.env.example` to `.env` and set provider keys if using a live provider:
```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Host IP address to bind |
| `PORT` | `8000` | Port to expose |
| `LLM_PROVIDER` | `gemini` | Provider: `gemini`, `openai`, or `fake` |
| `GEMINI_API_KEY` | `""` | Google Gemini API key (when using gemini) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `OPENAI_API_KEY` | `""` | OpenAI API key (when using openai) |
| `OPENAI_BASE_URL`| `https://api.openai.com/v1` | OpenAI API base URL |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `REQUEST_TIMEOUT_SECONDS` | `28.0` | Request timeout limit (judge hard limit 30s) |
| `LLM_TIMEOUT_SECONDS` | `8.0` | LLM call timeout limit |
| `LLM_MAX_RETRIES` | `1` | Max retry attempts for repairable errors |
| `SOLVER_TIMEOUT_SECONDS` | `5.0` | Solver execution budget |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### 7.4 Start the Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 8. Verification & Testing

### 8.1 Run Complete Automated Test Suite
Runs all 64 unit, integration, edge-case, and concurrency tests in `< 0.2s`:
```bash
python3 scripts/run_tests.py
```
*(Also compatible with `pytest`)*

### 8.2 Run All 10 Public Sample Cases
Validates all 10 cases from `docs/BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json` against organizer ground truth, replaying every schedule and checking optimal cost within official tolerance:
```bash
python3 scripts/run_public_samples.py
```

Expected output:
```text
========================================================
   GridWise Public Sample Pack Acceptance Test (10 Cases)
========================================================

[PASS] SAMPLE-01 (Case 01): Cost=38365.00 BDT (Exp: 38365.00, Diff: 0.0000) | Grid=2692.5 kWh | Peak=187.5 kWh | Interpretation: OK
[PASS] SAMPLE-02 (Case 02): Cost=42885.00 BDT (Exp: 42885.00, Diff: 0.0000) | Grid=2915.0 kWh | Peak=180.0 kWh | Interpretation: OK
[PASS] SAMPLE-03 (Case 03): Cost=35480.00 BDT (Exp: 35480.00, Diff: 0.0000) | Grid=2430.0 kWh | Peak=205.0 kWh | Interpretation: OK
[PASS] SAMPLE-04 (Case 04): Cost=40495.00 BDT (Exp: 40495.00, Diff: 0.0000) | Grid=2645.0 kWh | Peak=225.0 kWh | Interpretation: OK
[PASS] SAMPLE-05 (Case 05): Cost=33950.00 BDT (Exp: 33950.00, Diff: 0.0000) | Grid=2430.0 kWh | Peak=175.0 kWh | Interpretation: OK
[PASS] SAMPLE-06 (Case 06): Cost=34090.00 BDT (Exp: 34090.00, Diff: 0.0000) | Grid=2395.0 kWh | Peak=175.0 kWh | Interpretation: OK
[PASS] SAMPLE-07 (Case 07): Cost=38550.00 BDT (Exp: 38550.00, Diff: 0.0000) | Grid=2560.0 kWh | Peak=185.0 kWh | Interpretation: OK
[PASS] SAMPLE-08 (Case 08): Cost=37665.00 BDT (Exp: 37665.00, Diff: 0.0000) | Grid=2490.0 kWh | Peak=210.0 kWh | Interpretation: OK
[PASS] SAMPLE-09 (Case 09): Cost=34873.00 BDT (Exp: 34873.00, Diff: 0.0000) | Grid=2504.0 kWh | Peak=170.0 kWh | Interpretation: OK
[PASS] SAMPLE-10 (Case 10): Cost=41620.00 BDT (Exp: 41620.00, Diff: 0.0000) | Grid=2715.0 kWh | Peak=190.0 kWh | Interpretation: OK

========================================================
 RESULT: ALL 10 PUBLIC CASES PASSED OPTIMALITY & REPLAY!
========================================================
```

---

## 9. API Examples

### 9.1 `GET /health`
```bash
curl -s http://localhost:8000/health
```
Response:
```json
{"status":"ok"}
```

### 9.2 `POST /optimize-energy`
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "DEMO-01",
    "operator_notes": [
      "The battery charger will be isolated from 2 AM until 5 AM for electrical maintenance."
    ],
    "hours": [
      {"hour": 0, "demand_kwh": 80.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 1, "demand_kwh": 70.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 2, "demand_kwh": 65.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 3, "demand_kwh": 60.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 4, "demand_kwh": 60.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 5, "demand_kwh": 70.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0},
      {"hour": 6, "demand_kwh": 90.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 7, "demand_kwh": 110.0, "solar_kwh": 20.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 8, "demand_kwh": 140.0, "solar_kwh": 40.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 9, "demand_kwh": 160.0, "solar_kwh": 60.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 10, "demand_kwh": 170.0, "solar_kwh": 80.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 11, "demand_kwh": 180.0, "solar_kwh": 90.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 12, "demand_kwh": 175.0, "solar_kwh": 95.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 13, "demand_kwh": 170.0, "solar_kwh": 90.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 14, "demand_kwh": 160.0, "solar_kwh": 75.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 15, "demand_kwh": 150.0, "solar_kwh": 55.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 16, "demand_kwh": 140.0, "solar_kwh": 30.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 17, "demand_kwh": 150.0, "solar_kwh": 10.0, "tariff_bdt_per_kwh": 18.0},
      {"hour": 18, "demand_kwh": 180.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0},
      {"hour": 19, "demand_kwh": 190.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0},
      {"hour": 20, "demand_kwh": 175.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0},
      {"hour": 21, "demand_kwh": 160.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 18.0},
      {"hour": 22, "demand_kwh": 130.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 12.0},
      {"hour": 23, "demand_kwh": 100.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 8.0}
    ],
    "battery": {
      "capacity_kwh": 200.0,
      "initial_energy_kwh": 80.0,
      "minimum_energy_kwh": 20.0,
      "max_charge_kwh_per_hour": 50.0,
      "max_discharge_kwh_per_hour": 50.0
    }
  }'
```

Response:
```json
{
  "scenario_id": "DEMO-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "no_charge_window",
      "structured_adjustment": {"hours": [2, 3, 4]},
      "explanation": "Battery charging disabled during window."
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 130.0,
      "solar_used_kwh": 0.0,
      "battery_action": "charge",
      "battery_kwh": 50.0,
      "battery_energy_after_kwh": 130.0
    }
  ],
  "total_grid_kwh": 2235.0,
  "total_cost_bdt": 29880.0,
  "peak_grid_kwh": 175.0,
  "plan_summary": "24-hour cost-optimal schedule computed in 3.2ms. Active directives applied: no_charge_window. Total grid import: 2235.00 kWh, Total cost: 29880.00 BDT, Peak grid import: 175.00 kWh."
}
```

---

## 10. Docker Build & Deployment

### 10.1 Build Container Image
```bash
docker build -t gridwise-service:latest .
```

### 10.2 Run Container
```bash
docker run -d --name gridwise-app \
  -p 8000:8000 \
  -e LLM_PROVIDER=gemini \
  -e GEMINI_API_KEY="YOUR_API_KEY" \
  gridwise-service:latest
```

### 10.3 Verify Health
```bash
docker inspect --format='{{json .State.Health.Status}}' gridwise-app
# Output: "healthy"
```

---

## 11. External Tools & Dependencies Credit

We gratefully acknowledge the open-source libraries and algorithms powering GridWise:
- **FastAPI** by Sebastián Ramírez (Starlette & Pydantic)
- **Pydantic** for deterministic data validation and schema serialization
- **SciPy & NumPy** (`scipy.optimize.linprog`) powered by the **HiGHS** linear programming solver
- **Uvicorn** for high-performance ASGI server delivery
- **Google Gemini & OpenAI APIs** for generative natural-language directive parsing

---

## 12. Security & Known Limitations

### Security
- Zero secrets committed to the repository or baked into Docker layers.
- Strict structured logging automatically redacts tokens, headers, and credentials.
- Error handlers return safe machine codes (`400`, `422`, `500`) without leaking prompts, provider responses, or stack traces.

### Known Limitations
- Single 24-hour horizon per request (multi-day rolling horizon is out of scope per problem statement).
- Grid export is not supported (all surplus solar is curtailed).
- Battery round-trip efficiency is idealized at 100% per organizer model.
