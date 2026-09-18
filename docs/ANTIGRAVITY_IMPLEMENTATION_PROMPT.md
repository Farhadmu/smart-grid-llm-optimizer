# Antigravity implementation prompt

Copy the prompt below into Antigravity when the team is ready to begin implementation.

---

You are the lead implementation agent for our BUP CSE Fest 2026 GridWise Hackathon preliminary solution.

Implement the application in this repository. The specification phase is complete. Treat the following file as the implementation contract:

- `docs/GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`

Also read all three organizer artifacts in `docs/` before writing code:

- `BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf`
- `BUP_CSE_FEST_2026_Participant_Guide_&_Evaluation_Rubric_GridWise_LLM.pdf`
- `BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`

Authority order is: latest organizer clarification/judge package, the canonical organizer document for the topic, the internal specification, then public sample behavior. If you discover a material conflict, stop and report it with exact file/page/section evidence before implementing the disputed behavior. Do not silently reinterpret the contract.

Build a production-ready, public JSON HTTP service with exactly:

- `GET /health` -> HTTP 200 and `{"status":"ok"}` when ready.
- `POST /optimize-energy` -> validates one scenario, uses a real language-capable generative model to interpret every operator note, deterministically validates the model output, compiles directives, solves a cost-minimal 24-hour plan, independently replays the emitted plan, recalculates totals, and returns the exact success schema.

Non-negotiable constraints:

1. The LLM must directly produce the `directive_interpretation` that becomes optimizer constraints. Regex/phrase matching may assist normalization but cannot be the sole interpreter. Do not use the LLM as the optimizer.
2. Treat model output as untrusted. Enforce the exact six directive types, note-index bijection/order, `applies` semantics, structured-adjustment shapes, hour normalization, and numeric ranges before optimization.
3. Never silently convert invalid model output to `no_op` or invent a directive. Use the bounded recovery and safe-failure policy in the specification.
4. Use a deterministic linear optimizer with a signed battery-flow variable, all battery/solar/grid/directive constraints, and end-of-day battery neutrality.
5. Independently replay every successful plan after numeric cleanup. Never return a plan that fails replay.
6. Do not hard-code public phrases, case IDs, numeric values, schedules, or reference totals. Equivalent optimal schedules are allowed.
7. No UI, database, authentication, or unrelated features.
8. No secrets in code, tests, fixtures, Docker layers, logs, or README. All provider settings must be environment-driven and documented.
9. Meet the 30-second hard timeout and target p95 below 5 seconds. Health must not call external providers.
10. Preserve organizer field names and enum strings exactly. Avoid extra success fields.

Use a simple, maintainable stack suitable for a four-hour hackathon and reliable judging. A Python service with FastAPI, Pydantic, a provider-abstracted structured-output LLM client, and a mature LP solver is a good default, but you may choose an equivalent stack if it clearly improves reliability. Keep provider-specific code behind an interface so tests can use a deterministic fake interpreter while production uses the configured real model. The production path must not bypass the real model requirement.

Before implementation, inspect the repository and create a short execution plan mapped to the specification. Then implement in small, verifiable increments:

1. Project skeleton, configuration, exact API models, and controlled errors.
2. LLM provider interface, structured prompt/schema, guardrail validator, and bounded retry.
3. Directive compiler with the specified overlap policy.
4. LP optimizer and solution mapping.
5. Independent replay validator and totals calculation.
6. Endpoint orchestration, safe logging, time budgets, and concurrency behavior.
7. Unit, integration, property/edge, and failure-path tests.
8. Public sample runner covering all ten cases.
9. Docker image, health check, and clean-start verification.
10. Excellent self-contained README matching the organizer checklist.

Testing requirements:

- Make deterministic unit tests independent of external model availability.
- Add live-provider smoke tests behind an explicit opt-in environment flag; never run them by default or require secrets for the normal test suite.
- Test each directive and paraphrase/normalization category, all guardrail failures, every energy invariant, malformed requests, provider failures, solver failures, repeated requests, and numeric cleanup.
- Run every public sample input. Compare machine-checkable interpretation fields to organizer ground truth, replay the returned plan using ground-truth directives, and verify optimal cost within tolerance. Do not require byte-for-byte equality of hourly actions or explanation text.
- Include a test proving percentage semantics: “80% reduction” -> factor 0.2, and a capacity-relative reserve test matching SAMPLE-03.
- Include a test for final battery neutrality and one that catches reported-total drift after output rounding.

Required handoff artifacts:

- complete application source;
- locked/reproducible dependencies;
- test suite and one-command test runner;
- public sample validation command;
- production Dockerfile and documented pull/run equivalent;
- `.env.example` containing names/placeholders only;
- README with architecture, configuration, exact local/container commands, curl examples, model/guardrail/optimizer roles, dependencies, limitations, security guidance, and troubleshooting;
- concise final report listing changed files, verification commands and results, remaining risks, and deployment inputs still needed from the team.

Do not claim completion until tests pass, all ten public samples pass deterministic replay and cost checks, the container becomes healthy from a clean build, and no secret or hard-coded-case scan finds issues. If a required dependency or provider credential is unavailable, complete everything that can be tested with the fake provider, clearly identify the single blocked live check, and give the exact command the team should run after supplying credentials.

---
