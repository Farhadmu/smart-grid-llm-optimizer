# Prompt for Member 2 - Frontend

You are Member 2, the frontend owner for the BUP CSE Fest 2026 GridWise project.

Read `docs/team/TEAM_EXECUTION_PLAN.md`, `docs/team/MEMBER_2_FRONTEND.md`, `docs/GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`, the organizer artifacts, and the backend examples in `README.md` before editing.

Build an optional, polished demonstration dashboard entirely under `frontend/**`. It must consume the existing backend contract without changing it and must never become part of the judge's required path.

Implement:

- configurable API base URL;
- health status;
- complete scenario/note/hour/battery input experience;
- public-sample loader;
- exact request submission;
- loading, timeout, network, 400, 422, and 500 states;
- directive interpretation cards;
- complete hourly plan table;
- charts for demand, effective use, grid, tariff, and battery state;
- total grid, cost, peak, and plan summary;
- JSON inspector/copy/download;
- accessible responsive design suitable for the three-minute video.

Never call an LLM from the browser, embed a provider secret, interpret notes, repair schedules, modify field names, or hard-code expected schedules. Use typed API models generated or manually mirrored from the frozen contract. Keep mock fixtures clearly test-only.

Test the UI against both mock responses and the local backend. Verify at least one organizer public sample end to end. Document install, build, test, API-base configuration, and static deployment in `frontend/README.md`.

Finish with the standard handoff from `TEAM_EXECUTION_PLAN.md`, including build output location and the exact information needed by Members 1, 3, and 4.

