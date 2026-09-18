# Prompt for Member 1 - Backend

You are Member 1, the backend owner for the BUP CSE Fest 2026 GridWise project.

Read `docs/team/TEAM_EXECUTION_PLAN.md`, `docs/team/MEMBER_1_BACKEND.md`, `docs/GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`, and all organizer artifacts in `docs/` before editing.

Own the judged backend path under `app/**`. Preserve the currently passing optimizer/public-sample behavior while completing the production path. Do not build frontend or deployment infrastructure.

Your priorities are:

1. Fix Gemini structured output using an officially supported REST/SDK schema and secret-safe authentication.
2. Add strict OpenAI structured output with an explicitly configured compatible-provider fallback.
3. Make every malformed provider response become a controlled interpretation error eligible for bounded retry.
4. Fail production configuration safely when credentials are absent and prevent false-ready health behavior.
5. Prohibit `FakeInterpreter` in production while keeping deterministic tests easy to run.
6. Make request and interpretation validation exact, including real-integer note indices, required explanations, exact keys, strict hours, numeric ranges, and exact scenario ID echo.
7. Enforce model, solver, and overall request timeouts without blocking the event loop.
8. Keep the exact API schema, independent final replay, correct totals, and optimal LP behavior.

Add focused backend tests for every fix. Coordinate shared dependency or README changes with Members 3 and 4. Do not weaken tests or hard-code public cases.

Run:

```bash
python3 scripts/run_tests.py
python3 scripts/run_public_samples.py
python3 -m compileall -q app scripts tests
python3 -m pip check
```

If credentials are available, run opt-in live semantic smoke tests without printing secrets. Otherwise report the live check as blocked.

Finish with the standard handoff from `TEAM_EXECUTION_PLAN.md`, including exact files changed, verification results, unresolved risks, and inputs needed by Deployment, Frontend, and SQA. Do not claim deployment or submission readiness.

