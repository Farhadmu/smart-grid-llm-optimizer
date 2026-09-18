# Member 1 - Backend Workstream

## Mission

Own the complete judged request path from HTTP input through real LLM interpretation, deterministic guardrails, directive compilation, optimization, final replay, and exact response serialization.

## Owned files

- `app/**`
- Backend-specific unit tests created alongside backend fixes
- Backend sections of `README.md`, reviewed with Members 3 and 4

Avoid changing `frontend/**`, deployment manifests, or independent QA expectations without coordination.

## Immediate priorities

1. Repair Gemini structured-output transport using the currently supported official API representation.
2. Strengthen OpenAI structured output while retaining explicitly configured compatible-provider support.
3. Fix provider parsing so every malformed shape becomes `LLMInterpretationError` and participates in bounded retry.
4. Make readiness truthful when credentials or provider configuration are missing.
5. Prevent production from using `FakeInterpreter` accidentally.
6. Reject boolean note indices, missing explanations, extra interpretation fields, and all invalid adjustment shapes.
7. Make request schemas strict and preserve exact `scenario_id` echo semantics.
8. Enforce provider, solver, and overall request timeouts without blocking the event loop.
9. Preserve the independently replayed, cost-optimal behavior already passing public cases.

## Required backend tests

- Real-provider outgoing request contracts using mocked transports.
- Dictionary, list, scalar, null, malformed, empty, and provider-error responses.
- Successful one-retry repair and safe retry exhaustion.
- Credential and environment validation.
- Fake-provider production prohibition.
- Strict request and guardrail rejection cases.
- Solver timeout/status mapping and request timeout.
- Concurrency with slow provider and solver doubles.
- Exact successful response field set and exact `scenario_id` echo.

## Backend acceptance criteria

- Existing tests and public cases continue to pass.
- Selected production provider passes an opt-in live smoke test when credentials are supplied.
- No invalid LLM output reaches directive compilation.
- No successful plan can bypass independent replay.
- The event loop remains responsive during provider and solver work.
- Errors contain stable safe codes without secrets, prompts, raw model output, or stack traces.

## Handoff to other members

Provide:

- final environment-variable names and readiness rules to Member 3;
- frozen request/response examples and CORS decision to Member 2;
- provider doubles, error codes, and risk areas to Member 4.

