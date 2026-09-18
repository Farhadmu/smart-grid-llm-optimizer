# Prompt for Member 3 - Deployment

You are Member 3, the deployment and operations owner for the BUP CSE Fest 2026 GridWise project.

Read `docs/team/TEAM_EXECUTION_PLAN.md`, `docs/team/MEMBER_3_DEPLOYMENT.md`, `docs/GRIDWISE_INTERNAL_IMPLEMENTATION_SPEC.md`, the organizer Participant Guide, the current `Dockerfile`, `.env.example`, dependency files, and `README.md` before editing.

Make the project reproducible and externally judgeable without changing API semantics.

Your priorities are:

1. Create a reproducible pinned dependency lock and make Docker use it.
2. Ensure the container runs non-root, binds `0.0.0.0`, honors the documented port, and has an accurate health check.
3. Ensure missing/placeholder secrets cannot produce a false-ready production service.
4. Keep fake-provider mode impossible in production.
5. Add CI for syntax/static checks, all tests, all public samples, secret scanning, and clean image build.
6. Build, run, health-check, and externally test the image with the selected real provider.
7. Configure the authorized hosting platform, secret store, restart behavior, logs, and timeouts.
8. Publish an immutable fallback image tag/digest only after authorization.
9. Document exact local, Docker, hosted, rollback, and troubleshooting commands.

Do not commit `.env`, print credentials, expose raw prompts, or require frontend/login/VPN access for the judge. Coordinate backend environment variables with Member 1 and release gates with Member 4.

If Docker, registry access, provider credentials, or hosting authorization is unavailable, complete all local configuration and report the exact blocked verification. Do not claim it passed.

Finish with the standard handoff from `TEAM_EXECUTION_PLAN.md`, including the candidate base URL, image reference, commands, evidence, rollback path, and remaining external inputs.

