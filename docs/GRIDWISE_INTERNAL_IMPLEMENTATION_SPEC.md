# GridWise Hackathon - Internal Implementation Specification

**Project:** BUP CSE Fest 2026 - GridWise, Online Preliminary  
**Document status:** Implementation-ready internal specification  
**Prepared from:** organizer Problem Statement, Participant Guide & Evaluation Rubric, and public sample case pack  
**Source pack observed:** 18 September 2026; public sample pack version 2.0  
**Audience:** engineering, QA, DevOps, and the implementation agent  

> This document specifies what the team should build. It does not implement the application. Requirements marked **Organizer requirement** come directly from the supplied documents. Requirements marked **Internal decision** resolve an ambiguity or define a safer engineering standard. If an updated organizer artifact conflicts with this document, update this specification before changing the application.

## 1. Executive summary

Build one publicly reachable JSON-over-HTTP service with two exact routes:

- `GET /health` returns `200` and exactly `{"status":"ok"}` once the service is ready.
- `POST /optimize-energy` accepts one 24-hour energy scenario with 1-3 natural-language operator notes. It returns one structured interpretation per note and an optimal, valid 24-hour schedule.

The judged pipeline is:

1. Validate the request.
2. Use a language-capable generative model to interpret every operator note.
3. Treat the model output as untrusted data and validate it deterministically.
4. Compile the validated directives into mathematical constraints.
5. Optimize total grid-electricity cost.
6. Independently replay and validate the completed schedule.
7. Recalculate response totals from the emitted hourly plan.
8. Return the exact success schema.

Correctness gates optimization. A cheap plan gets no optimization credit for a case if it violates the organizer's ground-truth directive or any GridWise energy rule.

## 2. Requirement authority and conflict policy

| Topic | Canonical organizer source |
|---|---|
| Endpoints, request/response fields, directives, guardrails, battery behavior, energy accounting, optimization validity | Preliminary Problem Statement |
| Deployment, repository policy, submissions, performance, scoring, penalties, tie-breaks | Participant Guide & Evaluation Rubric |
| Worked examples and local validation data | Public Sample Cases JSON |

Conflict order inside the engineering project:

1. Latest organizer clarification or judge package, if issued.
2. Canonical organizer source listed above.
3. This internal specification.
4. Public sample behavior.
5. Implementation convenience.

The sample pack is evidence, not a substitute for the canonical documents. Exact public schedules must not be hard-coded.

## 3. Goals, non-goals, and scope

### 3.1 Required goals

- Interpret paraphrased, synthetic operator notes into one of six supported directive types.
- Preserve a one-to-one, ordered mapping between input notes and interpretation entries.
- Apply all relevant directives as hard constraints.
- Produce a mathematically valid and cost-minimal 24-hour schedule.
- Respond within the judge's operational limits and remain stable across repeated requests.
- Be reproducible locally and through a pullable Docker fallback image.
- Keep secrets out of source, images, logs, prompts exposed to clients, and responses.

### 3.2 Explicit non-goals

- No dashboard, web UI, authentication flow, user accounts, or database is required.
- No grid export, battery efficiency loss, degradation cost, demand charge, load shedding, or multi-day planning exists in the organizer model.
- No live campus, utility, billing, or personal data is needed.
- The LLM must not perform the mathematical optimization.
- The optimizer must not infer directives directly from raw prose.
- `plan_summary` is explanatory only; using AI only for it does not satisfy the LLM requirement.

## 4. External API contract

### 4.1 Transport conventions

**Organizer requirement**

- Public HTTP API, externally reachable without login, manual approval, VPN, or private networking.
- Exact route names and methods.
- JSON request and response bodies.
- One service deployment exposes both routes.

**Internal decision**

- Use `Content-Type: application/json; charset=utf-8` for JSON responses.
- Do not add success fields not listed in the organizer schema.
- Request validation is deterministic and occurs before any LLM call.
- Error responses use the internal envelope in section 4.4; the judge should rely on status codes, not error wording.

### 4.2 `GET /health`

Ready response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ok"}
```

Readiness target: available within 60 seconds of service start. Health must not call the model provider or optimizer, and it must remain fast even if the model provider is unavailable.

### 4.3 `POST /optimize-energy`

Success status: `200`.

The endpoint accepts exactly one scenario object, validates it, interprets all notes, solves one 24-hour schedule, validates the result, and returns the response described in section 6.

Operational limits:

- Hard judge timeout: 30 seconds per request.
- Latency scoring: p95 `<= 5 s` earns full latency points; `>5-15 s` partial; `>15-30 s` lower partial; `>30 s` zero and timeout failure.
- Internal target: p95 below 5 seconds with at least 20% timeout headroom.

### 4.4 Status codes and controlled errors

| Status | Use |
|---|---|
| `200` | Successful health or optimization response |
| `400` | Malformed JSON or structurally invalid request |
| `422` | Optional: well-formed JSON with semantic invalidity |
| `500` | Controlled internal/model/solver failure; never expose secrets or raw stack traces |

**Internal decision:** consistently use `400` for JSON syntax/type/shape errors and `422` for cross-field semantic errors. Use `500` after bounded model-output recovery or a solver/final-validation failure. A `503` may be operationally conventional but is not listed by the organizer; do not use it on the judged path unless an official clarification permits it.

Internal error shape:

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "Safe public description"
  }
}
```

Never return raw model output, prompts, provider responses, credentials, stack traces, or solver internals in an error.

## 5. Request schema and validation

### 5.1 Top-level request

```json
{
  "scenario_id": "GRID-101",
  "operator_notes": ["..."],
  "hours": ["24 hour objects"],
  "battery": {"battery fields": "..."}
}
```

| Field | Type | Rules |
|---|---|---|
| `scenario_id` | string | Required, non-empty synthetic scenario identifier |
| `operator_notes` | array of strings | Required; length 1-3; every entry non-empty natural language; order is significant |
| `hours` | array of hour objects | Required; exactly 24 entries; unique complete hour set 0-23 |
| `battery` | object | Required; exact fields in section 5.3 |

### 5.2 Hour object

| Field | Type | Rules |
|---|---|---|
| `hour` | integer | Unique value 0-23; input order must not be assumed |
| `demand_kwh` | number | Finite and non-negative |
| `solar_kwh` | number | Finite and non-negative; base availability before directives |
| `tariff_bdt_per_kwh` | number | Finite and non-negative |

Internally index by `hour`, not array position. Output is always sorted 0 through 23.

### 5.3 Battery object

| Field | Type | Rules |
|---|---|---|
| `capacity_kwh` | number | Finite and non-negative |
| `initial_energy_kwh` | number | Finite; `minimum_energy_kwh <= initial_energy_kwh <= capacity_kwh` |
| `minimum_energy_kwh` | number | Finite; `0 <= minimum_energy_kwh <= capacity_kwh` |
| `max_charge_kwh_per_hour` | number | Finite and non-negative |
| `max_discharge_kwh_per_hour` | number | Finite and non-negative |

The cross-field inequalities are an **internal decision** derived from the organizer's battery-validity rules. Reject invalid inputs before the model call.

### 5.4 Structural and semantic rejection list

Reject at minimum:

- missing required fields or wrong JSON types;
- booleans used where a number is expected;
- non-finite values, including NaN or infinity if the JSON parser/provider permits them;
- negative energy, rate, capacity, or tariff values;
- anything other than 24 hour objects;
- duplicate, missing, fractional, or out-of-range hour identifiers;
- zero, more than three, empty, or whitespace-only operator notes;
- battery minimum/initial energy outside capacity bounds.

## 6. Successful response schema

```json
{
  "scenario_id": "GRID-101",
  "directive_interpretation": [],
  "hourly_plan": [],
  "total_grid_kwh": 0,
  "total_cost_bdt": 0,
  "peak_grid_kwh": 0,
  "plan_summary": "..."
}
```

| Field | Type | Requirement |
|---|---|---|
| `scenario_id` | string | Exact echo of request value |
| `directive_interpretation` | array | Exactly one entry per note, ordered by `note_index` 0..N-1 |
| `hourly_plan` | array of 24 objects | Exactly one unique entry for every hour 0-23, sorted ascending internally |
| `total_grid_kwh` | number | Sum of emitted `grid_kwh` values |
| `total_cost_bdt` | number | Sum of emitted `grid_kwh * input tariff` by hour |
| `peak_grid_kwh` | number | Maximum emitted `grid_kwh` |
| `plan_summary` | string | Short human-readable strategy explanation; not used as machine truth |

### 6.1 Directive interpretation entry

| Field | Type | Requirement |
|---|---|---|
| `note_index` | integer | Existing zero-based input note index; each index appears exactly once |
| `applies` | boolean | `false` only for `no_op`; `true` for every other type |
| `directive_type` | enum | One of the exact six values in section 7 |
| `structured_adjustment` | object or null | Exact shape for the directive; null only for `no_op` |
| `explanation` | string | Short explanation; exact wording is not scored |

### 6.2 Hourly plan entry

| Field | Type | Requirement |
|---|---|---|
| `hour` | integer | 0-23, unique |
| `grid_kwh` | number | Finite, non-negative grid import |
| `solar_used_kwh` | number | Finite, non-negative, not above effective solar |
| `battery_action` | enum | Exactly `charge`, `discharge`, or `idle` |
| `battery_kwh` | number | Finite, non-negative action magnitude; 0 when idle |
| `battery_energy_after_kwh` | number | Battery energy immediately after the hour |

**Internal canonicalization:** if the solved battery flow has absolute magnitude below the internal epsilon, emit `idle` and `battery_kwh = 0`. Never emit zero-magnitude `charge` or `discharge` actions.

## 7. Supported directives

No other directive type is allowed.

### 7.1 `solar_reduction`

```json
{
  "hours": [13, 14],
  "factor": 0.2
}
```

- `factor` is the usable fraction remaining, not the percentage reduction.
- Valid range: inclusive 0 through 1.
- Example: an 80% reduction means factor `0.2`.
- For every affected hour: `effective_solar[h] = original_solar[h] * factor`.

### 7.2 `minimum_battery_reserve`

```json
{
  "hours": [18, 19, 20],
  "minimum_energy_kwh": 120
}
```

- Value must be finite, non-negative, and no greater than battery capacity.
- The requirement applies to `battery_energy_after_kwh` in each listed hour.
- Active lower bound is the larger of the base minimum and directive reserve.
- Percentage language must be converted using scenario battery capacity. Public SAMPLE-03 maps 50% of 200 kWh to 100 kWh.

### 7.3 `no_charge_window`

```json
{"hours": [14, 15]}
```

Battery charging magnitude must be zero in every listed hour.

### 7.4 `no_discharge_window`

```json
{"hours": [17, 18]}
```

Battery discharging magnitude must be zero in every listed hour.

### 7.5 `max_grid_window`

```json
{
  "hours": [18, 19, 20],
  "max_grid_kwh": 155
}
```

Grid import must be at or below the cap independently in every listed hour. The cap must be finite and non-negative.

### 7.6 `no_op`

```json
{
  "applies": false,
  "directive_type": "no_op",
  "structured_adjustment": null
}
```

Use for a note that does not affect the current 24-hour energy schedule. It changes no optimization constraint.

## 8. Time, numeric, and language normalization

### 8.1 Whole-hour windows

- Windows are start-inclusive and end-exclusive.
- `1 PM to 3 PM` maps to `[13, 14]`.
- `noon until 2 PM` maps to `[12, 13]`.
- Returned hour arrays must contain unique integers, sorted ascending, each in 0-23.
- A window crossing midnight should wrap within the 24-hour horizon, for example 10 PM to 2 AM -> `[0, 1, 22, 23]` after required ascending sort. This is an **internal decision**; no supplied organizer example crosses midnight. Add a test and seek clarification if possible.
- Ambiguous time language must be resolved by the LLM using the scenario's single-day, hourly context. The model must not invent minute-level intervals.

### 8.2 Numeric language

- `about`, `roughly`, `approximately`, `one-fifth`, percentages, and equivalent descriptions still produce a concrete numeric value.
- Solar language distinguishes “reduced **to** X%” (factor X/100) from “reduced **by** X%” (factor 1-X/100).
- Reserve percentages are percentages of `capacity_kwh`, unless wording explicitly states another base.
- Returned directive numbers must be finite and within directive-specific bounds.

### 8.3 Judge tolerance and internal precision

- Organizer default equivalence tolerance: absolute difference `<= 0.01 kWh` or `<= 0.01 BDT`, unless the official judge package is stricter.
- Do not design to the edge of that tolerance.
- **Internal decision:** solve and replay using full double precision; use an internal validation epsilon at most `1e-7` where practical; normalize `-0.0` to `0.0`; emit a stable number of decimal places without premature rounding; recalculate totals from the final emitted plan.

## 9. LLM interpretation subsystem

### 9.1 Mandatory role

The language-capable generative model must directly produce the structured interpretation used to build optimizer constraints. Hard-coded phrase matching as the sole interpreter is non-compliant. Deterministic preprocessing and postprocessing may normalize input and validate output but may not replace the model interpretation step.

### 9.2 Model input

Provide the model only the information needed to interpret notes correctly:

- ordered operator notes with explicit indices;
- the six allowed directive types and exact adjustment shapes;
- whole-hour, percentage, and `no_op` semantics;
- battery capacity when percentage reserve language may depend on it;
- explicit instruction not to modify demand, solar base values, tariff, or battery parameters;
- explicit instruction to return one entry per note in note-index order.

Passing the full 24-hour numeric arrays is unnecessary for most interpretation and increases latency/cost. If passed, clearly label them as immutable context.

### 9.3 Model output contract

Prefer provider-supported structured generation or tool/function calling with a strict schema. The raw model response must never flow directly to the optimizer.

Required model-output invariants:

- JSON/structured data only;
- array length equals input note count;
- indices form exactly 0..N-1 in order;
- exact enum and exact adjustment shape;
- no unexpected constraint fields;
- explanations are short and contain no secrets.

### 9.4 Deterministic guardrail validator

Validate all of the following before constraint compilation:

1. Parseability and root shape.
2. Exact interpretation count and note-index bijection/order.
3. Allowed directive enum.
4. `applies` semantics.
5. `structured_adjustment` null/object semantics and exact keys.
6. Hours type, uniqueness, bounds, non-emptiness, and ascending order.
7. Solar factor inclusive 0..1.
8. Reserve finite, non-negative, and within capacity.
9. Grid cap finite and non-negative.
10. No changes to base scenario data and no unsupported directive.

Do not silently repair semantic errors such as an unsupported type, wrong note mapping, or out-of-range factor. Sorting an otherwise correct hour set or normalizing harmless numeric representation is acceptable only if the raw output is retained internally for diagnostics and the action is tested.

### 9.5 Recovery policy

**Internal decision:** make at most one bounded repair/retry call with deterministic validation errors fed back in a secret-safe form. The total request must remain within the 30-second limit and target p95 below 5 seconds. If output is still invalid, return a controlled `500`; do not invent a directive, downgrade the note to `no_op`, or optimize without the note.

Provider failures, rate limits, malformed responses, and timeouts must not crash the process. Use explicit connect/read deadlines, bounded retries, and no unbounded exponential backoff inside a judged request.

## 10. Directive compilation

Convert validated interpretations into per-hour arrays used by the optimizer:

- `effective_solar[h]`
- `active_min_energy[h]`
- `charge_allowed[h]`
- `discharge_allowed[h]`
- `grid_cap[h]`, where absent means unbounded

### 10.1 Combination policy

The organizer guarantees feasible scoring scenarios and no mutually contradictory hard directives. It does not fully specify multiple overlapping directives of the same type. Use the following conservative intersection policy (**internal decision**):

- overlapping solar reductions: use the smallest factor for that hour;
- overlapping reserves: use the maximum reserve;
- overlapping grid caps: use the minimum cap;
- any active no-charge directive disables charging;
- any active no-discharge directive disables discharging;
- if both no-charge and no-discharge apply, battery flow is zero.

This satisfies every individual hard limit without inventing a weaker constraint. Do not multiply overlapping solar factors unless the organizer explicitly clarifies cumulative reductions.

## 11. Optimization model

### 11.1 Inputs and variables

For each hour `h in 0..23`, organizer inputs are:

- `D[h]`: demand kWh
- `S[h]`: compiled effective solar kWh
- `T[h]`: grid tariff BDT/kWh
- battery capacity `C`, initial energy `E_init`, base/compiled minimum `E_min[h]`, charge limit `R_c`, discharge limit `R_d`

Decision variables:

- `G[h] >= 0`: grid import
- `U[h] >= 0`: solar used
- `X[h]`: signed battery flow, positive for charge and negative for discharge
- `E[h]`: battery energy after hour `h`

Using one signed battery-flow variable makes charging and discharging mutually exclusive without binary variables.

### 11.2 Objective

Minimize:

```text
sum(h=0..23, G[h] * T[h])
```

There is no secondary objective in the organizer contract. Equivalent optimal schedules are accepted.

### 11.3 Constraints

For all hours:

```text
G[h] + U[h] = D[h] + X[h]
0 <= U[h] <= S[h]
-R_d <= X[h] <= R_c
E[h] = (E_init if h = 0 else E[h-1]) + X[h]
E_min[h] <= E[h] <= C
G[h] >= 0
```

Directive constraints:

```text
if charge is forbidden at h:     X[h] <= 0
if discharge is forbidden at h:  X[h] >= 0
if grid cap exists at h:          G[h] <= grid_cap[h]
```

End-of-day neutrality:

```text
E[23] = E_init
```

This is a linear program. Use a mature deterministic LP solver. Verify the solver reports an optimal solution; infeasible, unbounded, iteration-limit, or numerical-failure statuses must become controlled internal failures, never partial plans.

### 11.4 Solution-to-response mapping

For each hour:

- if `X[h] > epsilon`: `battery_action = "charge"`, `battery_kwh = X[h]`;
- if `X[h] < -epsilon`: `battery_action = "discharge"`, `battery_kwh = -X[h]`;
- otherwise: `battery_action = "idle"`, `battery_kwh = 0`.

Set `battery_energy_after_kwh = E[h]`, `grid_kwh = G[h]`, and `solar_used_kwh = U[h]` after numeric cleanup.

## 12. Mandatory final replay validator

The final validator must be independent of the optimizer's constraint-building code as far as practical. Treat `hourly_plan` as the source of truth and replay it chronologically against the original request plus compiled directives.

Fail closed unless all checks pass:

1. Exactly 24 unique plan hours covering 0-23.
2. All required numeric values finite and non-negative.
3. Valid action enum and canonical action/magnitude consistency.
4. Battery transition:
   - charge: `E_after = E_before + battery_kwh`;
   - discharge: `E_after = E_before - battery_kwh`;
   - idle: `E_after = E_before` and `battery_kwh = 0`.
5. Charge/discharge hourly rate limits.
6. Battery compiled minimum and capacity bounds after every hour.
7. No-charge/no-discharge directive compliance.
8. `0 <= solar_used <= effective_solar`.
9. Grid cap compliance.
10. Hourly energy balance:

```text
grid + solar_used + battery_discharge
= demand + battery_charge
```

11. Final energy equals initial energy.
12. Recomputed `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` match the values to be returned.

If cleanup/rounding changes any plan value, replay the cleaned plan and derive totals only afterward.

## 13. Reliability, security, and observability

### 13.1 Reliability

- Keep model and solver time budgets separate and bounded.
- Ensure repeated valid requests do not leak state between scenarios.
- Make request handling concurrency-safe.
- Do not require runtime training or fine-tuning.
- Cache only if it cannot cross-contaminate scenarios; include all interpretation-relevant context in cache keys.
- Gracefully handle client cancellation and provider/solver exceptions.

### 13.2 Security

- Load secrets only from environment or platform secret management.
- Never bake credentials into Docker layers.
- Never commit `.env`, API keys, tokens, passwords, or secret-bearing logs.
- Redact authorization headers and provider payloads.
- Do not return raw stack traces.
- Credit external libraries, APIs, SDKs, and AI tools in `README.md`.

### 13.3 Logging and metrics

Use structured logs with:

- generated request/correlation ID;
- scenario ID after safe length/control-character handling;
- validation stage and stable failure code;
- model and solver latency;
- retry count;
- solver status;
- final replay pass/fail.

Do not log credentials, raw authorization headers, secret environment values, or unrestricted raw provider payloads. Operator notes are synthetic, but logging them is not required for judging; prefer hashes or debug-only redacted logs.

Track at least request count, status class, latency distribution, model failures, guardrail failures, solver failures, and final replay failures.

## 14. Test strategy and acceptance matrix

### 14.1 Request contract tests

- Valid canonical request.
- Hours supplied out of order but complete.
- Missing/duplicate/out-of-range/fractional hour.
- 0 and 4 operator notes; blank note.
- Wrong types, booleans-as-numbers, negatives, NaN/infinity if accepted by parser.
- Invalid battery bounds and rates.
- Malformed JSON produces controlled `400`.

### 14.2 Interpretation tests

For every directive type:

- canonical phrase;
- multiple paraphrases;
- distractor/no-op phrase;
- AM/PM, noon, midnight, 24-hour notation;
- start-inclusive/end-exclusive mapping;
- “reduced to” versus “reduced by” percentages;
- fractional descriptions such as “one-fifth” and “half”;
- capacity-relative reserve;
- 1, 2, and 3 notes with exact ordering.

Guardrail negatives:

- missing/duplicate/wrong note index;
- unsupported type;
- wrong `applies` value;
- null adjustment on active directive;
- extra/missing adjustment fields;
- unsorted/duplicate/out-of-range hours;
- factor outside 0..1;
- reserve above capacity;
- negative/non-finite cap;
- malformed model output twice -> controlled failure.

### 14.3 Optimizer and replay tests

- No directives.
- Each directive independently.
- All compatible combinations represented by public cases.
- Battery starts at minimum and at capacity.
- Zero charge/discharge rates.
- Zero demand, zero solar, zero tariffs, and equal tariffs.
- Solar surplus and curtailment.
- Binding grid cap.
- Both charge and discharge forbidden in the same hour.
- Exact reserve boundary.
- End-of-day restoration requiring late charge.
- Multiple optimal schedules.
- Deliberately infeasible internal fixture -> controlled failure.
- Property tests generating feasible scenarios and checking every replay invariant.

### 14.4 Public sample pack acceptance

Run all ten inputs from `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`.

For each case require:

- interpretation matches organizer ground truth for `applies`, type, hours, and numeric values within tolerance;
- explanation need not match text exactly;
- returned plan passes replay using ground-truth directives;
- recalculated cost is optimal within official tolerance;
- exact hourly actions need not match the reference schedule.

Independent specification audit result: all 10 supplied reference outputs pass directive application, hourly energy balance, effective-solar bounds, battery transitions/bounds/rates, end-of-day neutrality, and reported total/cost/peak recalculation at 0.01 tolerance.

### 14.5 Operational acceptance

- Health ready within 60 seconds.
- Repeated external POST calls remain below 30 seconds; target p95 below 5 seconds.
- Valid requests do not yield 5xx, invalid JSON, or no response under expected concurrency.
- Service restarts cleanly.
- Docker image pulls by exact tag/digest, binds `0.0.0.0`, exposes documented port, and becomes healthy with the documented command.

## 15. Recommended component boundaries

Keep these units independently testable:

1. API/request models and error mapper.
2. Request semantic validator.
3. LLM provider interface.
4. Prompt/schema builder.
5. Interpretation guardrail validator.
6. Directive compiler.
7. Optimizer adapter.
8. Plan serializer/numeric cleaner.
9. Independent replay validator and totals calculator.
10. Service orchestration layer.
11. Observability and configuration.

Recommended dependency direction:

```text
HTTP -> request validation -> LLM interpreter -> guardrails
     -> directive compiler -> optimizer -> numeric cleanup
     -> independent replay/totals -> response
```

The optimizer accepts only structured scenario data and validated directives. It must never depend on raw note text or provider-specific response objects.

## 16. Configuration contract

Names may vary by implementation, but the README must document every required variable without secret values. At minimum configure:

- model provider/base URL if applicable;
- model identifier;
- model API key/credential variable;
- model connect/read timeout;
- service host (`0.0.0.0` in containers) and port;
- log level;
- bounded retry count;
- optional deterministic model parameters.

Fail startup clearly if required configuration is missing, except that `/health` must not claim ready before the service can serve judged requests. Do not leak the missing secret's value.

## 17. Deliverables and repository requirements

The completed project must include:

- working public base URL with both endpoints;
- source repository created after question reveal, private during the event, public after the submission deadline;
- complete source and dependency/configuration files;
- self-contained `README.md`;
- pullable, tested Docker fallback image with exact tag or digest;
- maximum 3-minute architecture/solution video.

README checklist:

- clean clone/pull and local setup;
- required environment-variable names, without values;
- model/provider or local model identifier;
- explicit LLM role in note interpretation;
- guardrail and optimizer/solver explanation;
- exact start command;
- `GET /health` example;
- `POST /optimize-energy` example;
- public-sample test command and expected interpretation/cost-validation behavior;
- Docker pull/run command, port, and health check;
- dependencies and external-tool credits;
- known limitations and secret-handling guidance.

## 18. Scoring priorities

Base score: 100 points.

| Category | Points |
|---|---:|
| LLM directive interpretation | 25 |
| Directive application and constraint correctness | 25 |
| Optimization quality | 10 |
| API contract and schema | 10 |
| Performance and reliability | 10 |
| Deployment and Docker fallback | 10 |
| Documentation and local reproducibility | 10 |

Optimization quality for valid hidden cases is described as:

```text
quality_ratio = min(1, organizer_optimal_cost / recalculated_team_cost)
Optimization Quality = 10 * average(quality_ratio)
```

If both costs are within tolerance of zero, ratio is 1. The organizer PDF's next clause is visibly truncated after the word `quality_ratio`. **Internal interpretation:** when organizer optimum is within tolerance of zero and team cost is above tolerance, ratio is 0. Seek organizer clarification if possible.

The video contributes no base points and is the first tie-breaker. Remaining tie-break sequence: directive application/correctness, LLM interpretation, optimization quality, API/schema, reliability/deployment, documentation/reproducibility, exceptional engineering/verification.

## 19. Open ambiguities and adopted decisions

| Ambiguity | Internal decision | Risk/mitigation |
|---|---|---|
| Multiple overlapping directives of the same type | Use intersection policy in section 10.1 | Safest way to satisfy every hard directive; ask organizer if opportunity arises |
| Window crossing midnight | Wrap and then return sorted unique hours | No public example; test explicitly and seek clarification |
| Zero-magnitude charge/discharge action | Canonicalize to `idle` | Aligns action-consistency scoring and all public samples |
| Model output cannot be validated after retry | Controlled `500`; never invent/no-op fallback | Meets safe-failure requirement; may lose the case but protects correctness |
| Error response body | Stable internal envelope | Organizer specifies codes, not body |
| Zero-optimum quality formula | Positive team cost -> ratio 0 | Organizer sentence is truncated; mathematically consistent |
| Strictness of numeric tolerance | Validate internally far tighter than 0.01 | Avoid edge failures if judge package is stricter |
| Extra request fields | Prefer strict request models in judged service | Exact schema is required; revisit if judge examples include metadata |

## 20. Definition of done

Implementation is complete only when all conditions hold:

- Both endpoints exactly match the organizer contract.
- The LLM is demonstrably on the directive path used by the optimizer.
- Every LLM output passes deterministic guardrails before use.
- The LP model implements all base and directive constraints.
- Every successful result passes independent final replay.
- All ten public cases pass semantics, validity, totals, and optimal-cost checks without schedule hard-coding.
- Negative, malformed, provider-failure, solver-failure, and repeated-request tests pass safely.
- p95 target and hard timeout are verified in a representative deployment.
- Docker fallback and clean README quickstart are verified from a fresh environment.
- No secrets exist in repository history, image layers, logs, or public examples.
- Submission endpoint, repository visibility transition, Docker reference, and video remain accessible through evaluation.

