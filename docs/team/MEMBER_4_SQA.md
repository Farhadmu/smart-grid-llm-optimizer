# Member 4 - Software Quality Assurance Workstream

## Mission

Independently prove that the submitted system follows the organizer contract, survives hidden-like cases and failures, remains within operational limits, and is reproducible from the submitted artifacts.

## Owned files

- `tests/**`
- QA-specific scripts under `scripts/**`
- `docs/qa/**`
- CI test definitions coordinated with Member 3

Do not weaken assertions to match defective behavior. File a reproducible defect against the owning member.

## Test layers

### Contract and validation

- Exact endpoints, methods, status codes, JSON content type, and success field sets.
- Malformed JSON, missing fields, extra fields, wrong types, booleans-as-numbers, non-finite/negative values, and invalid battery relationships.
- Exactly 24 unique hours and 1-3 non-empty notes.
- Exact scenario ID echo.

### LLM and guardrails

- All six directive types and realistic paraphrases.
- Distractors, percentages, fractions, AM/PM/noon/midnight, and multi-note order.
- Provider request-contract tests for Gemini and OpenAI.
- Every malformed provider response shape.
- Boolean/duplicate/missing/out-of-order note indices.
- Invalid applies semantics, adjustment keys, hours, factors, reserves, caps, and explanations.
- Retry recovery and safe exhaustion.
- Opt-in live semantic suite for the selected production model.

### Optimizer and replay

- Each directive independently and compatible combinations.
- Organizer public cases using organizer ground truth.
- Zero demand/solar/tariff/rates, solar surplus, binding caps, reserve boundaries, multiple optima, and infeasible fixtures.
- Hourly balance, effective solar, battery transitions/bounds/rates, directive compliance, end neutrality, totals, cost, and peak.
- Rounding and tolerance adversarial tests.
- Property-based feasible scenarios where practical.

### Reliability and security

- Provider, solver, and overall request timeouts.
- Concurrent and repeated requests with isolation.
- p50/p95/max latency and failure rate.
- Missing credential and false-readiness behavior.
- Secret scanning of source, history, image layers, logs, and API errors.
- Dependency and container vulnerability review.

### Deployment and reproducibility

- Follow README from a clean environment without undocumented steps.
- Build and run the exact fallback image.
- Test public endpoint and container independently.
- Confirm no login/VPN/manual approval requirement.
- Verify all links and artifacts remain accessible.

## Defect severity

- **P0:** data/secret exposure, no viable judge path, or systematically invalid schedules.
- **P1:** production provider/deployment failure, incorrect directives, broken replay, false readiness, or timeout breach.
- **P2:** edge-case contract failure, misleading documentation, weak guardrail, or material reliability risk.
- **P3:** non-blocking polish or maintainability issue.

Every defect report includes severity, environment, exact reproduction, expected result, actual result, source requirement, logs without secrets, and owner.

## SQA acceptance output

Publish a release report containing:

- requirement-to-test traceability matrix;
- automated test totals and results;
- all ten public-case results;
- selected real-provider semantic results;
- latency and failure-rate results;
- container and public-endpoint evidence;
- security/reproducibility findings;
- open defects by severity;
- final recommendation: reject, conditional pass, or pass.

