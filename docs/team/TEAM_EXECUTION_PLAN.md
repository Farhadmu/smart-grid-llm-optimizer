# GridWise Four-Member Execution Plan

## Purpose

This plan divides the remaining GridWise work among four members without creating conflicting ownership. The organizer judges the public backend API; the frontend is an optional demonstration tool and must never become a dependency of the judging path.

## Shared source of truth

Everyone must read these files before starting:

1. `docs/GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`
2. `docs/BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf`
3. `docs/BUP_CSE_FEST_2026_Participant_Guide_&_Evaluation_Rubric_GridWise_LLM.pdf`
4. `docs/BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json`

Authority order:

1. Latest official organizer clarification or judge package.
2. The canonical organizer document for the relevant topic.
3. `GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`.
4. Public sample behavior.
5. Team implementation preference.

## Ownership map

| Area | Primary owner | Supporting reviewer | Write boundary |
|---|---|---|---|
| API, schemas, LLM providers, guardrails, orchestration, optimizer, replay | Member 1 - Backend | Member 4 | `app/**` and backend-focused tests |
| Optional dashboard/demo client | Member 2 - Frontend | Member 1 | `frontend/**` only |
| Docker, runtime configuration, CI, hosting, registry, operations | Member 3 - Deployment | Members 1 and 4 | `Dockerfile`, deployment files, CI, lock files, deployment documentation |
| Independent QA, contract tests, hidden-like cases, performance and release evidence | Member 4 - SQA | All members | `tests/**`, QA scripts and QA reports |

Shared files such as `README.md`, dependency manifests, and API examples require review by the affected owners before merge.

## Non-negotiable integration contract

- The judged backend exposes exactly `GET /health` and `POST /optimize-energy`.
- `GET /health` returns `{"status":"ok"}` only when the configured production service is ready.
- The frontend consumes the backend contract but cannot change it.
- The deployment must expose the backend directly. The frontend, reverse proxy, login, or dashboard cannot be required for judge access.
- SQA validates the backend through public HTTP behavior and does not trust internal implementation state.
- A real language-capable model must produce the structured directive interpretation used by the optimizer.
- Fake interpretation is permitted only in tests/development and must be impossible to enable accidentally in production.

## Current baseline

At the time of this split:

- 64 automated tests pass.
- All 10 public samples pass with the fake interpreter and optimal cost.
- The production-provider path still requires fixes and live verification.
- The Docker daemon was unavailable during the last audit, so no clean container build was verified.
- No live provider credentials, public endpoint, registry image reference, or final video have been verified.

Passing fake-provider tests do not prove production LLM correctness.

## Parallel work sequence

### Phase 1 - Contract freeze

- All members read the shared sources.
- Member 1 confirms the final request/response models.
- Member 2 creates frontend types and mocks from the frozen schema.
- Member 3 documents the target host, port, environment variables, registry, and provider-secret mechanism.
- Member 4 converts the organizer contract into a traceable test matrix.

### Phase 2 - Parallel implementation

- Member 1 repairs and completes backend production behavior.
- Member 2 builds the optional demo entirely under `frontend/` using a configurable API base URL.
- Member 3 prepares reproducible dependencies, Docker, CI, and deployment configuration without changing API behavior.
- Member 4 adds independent negative, provider-contract, replay, concurrency, timeout, and public-sample tests.

### Phase 3 - Integration

Merge order:

1. Backend contract and production-provider fixes.
2. SQA tests and backend fixes required by confirmed defects.
3. Dependency lock, container, CI, and deployment work.
4. Frontend integration against the deployed candidate.
5. Final documentation and submission artifacts.

### Phase 4 - Release gate

The team may call the project code-complete only when:

- all automated tests pass;
- all ten public cases pass interpretation, replay, and optimal-cost checks;
- the selected real provider passes live semantic smoke tests;
- production cannot use the fake interpreter accidentally;
- missing credentials cannot produce a false-ready service;
- the container builds from a clean context and becomes healthy;
- the deployed public endpoint passes external health and optimization checks;
- p95 latency is below 5 seconds and no request exceeds 30 seconds in the agreed test;
- no credentials exist in source, history, image layers, logs, or response bodies.

Submission-ready additionally requires:

- public endpoint URL;
- repository visibility changed according to organizer timing;
- pullable Docker image with exact tag or digest;
- complete README and configuration instructions;
- accessible maximum three-minute architecture/solution video.

## Coordination protocol

- Each member works in a separate branch or isolated worktree.
- Do not modify another member's owned directory without notifying them.
- Every handoff includes changed files, commands run, results, unresolved issues, and assumptions.
- A failing test is not weakened to make a build green. Fix the product or correct the test using organizer evidence.
- Never paste real secrets into chat, commits, screenshots, fixtures, or documentation.
- Material contract questions are recorded with exact source document and section references.

## Daily handoff template

```text
Owner:
Scope completed:
Files changed:
Verification commands:
Results:
Contract decisions:
Open defects/blockers:
Inputs needed from another member:
Safe merge order or conflicts:
```

