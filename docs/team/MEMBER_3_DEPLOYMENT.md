# Member 3 - Deployment Workstream

## Mission

Make the backend reproducible, securely configurable, externally reachable, observable, and recoverable through the required Docker fallback path.

## Owned files

- `Dockerfile`
- `.dockerignore`
- `.env.example`
- dependency lock files, coordinated with Member 1
- CI configuration
- `deployment/**` or equivalent infrastructure files
- deployment and operations sections of `README.md`

Do not change API behavior or model semantics without Member 1 review.

## Required work

1. Pin reproducible dependency versions and make the container install the lock.
2. Ensure the container runs as non-root, binds to `0.0.0.0`, and uses the documented port consistently.
3. Make runtime `HOST`/`PORT` behavior and the container health check agree.
4. Pass secrets only through the hosting platform's secret store or runtime environment.
5. Confirm fake-provider mode cannot be enabled in production.
6. Build a clean image and scan it for vulnerabilities and accidentally copied secrets.
7. Verify `/health` becomes ready within 60 seconds only with valid production configuration.
8. Verify `POST /optimize-energy` externally using the selected real provider.
9. Configure sensible restart, concurrency, request-size, and timeout behavior without exceeding the judge's 30-second limit.
10. Create CI stages for syntax/static checks, tests, public samples, secret scanning, and container build.
11. Publish the fallback image only after authorization, using an immutable tag or digest.
12. Record the public base URL, image reference, region, environment names, and rollback procedure without exposing values.

## Required operational checks

- Clean build without relying on local caches.
- Container starts from only documented environment variables.
- Health check and real optimization request succeed from outside the development environment.
- Repeated requests do not exhaust quotas, memory, workers, or file descriptors.
- Logs contain correlation IDs but no credentials or raw secret-bearing payloads.
- Public endpoint requires no login, VPN, dashboard, or manual approval.
- Image remains pullable throughout evaluation.

## Deployment acceptance criteria

- Exact reproducible build instructions.
- Working public backend URL.
- Pullable fallback image with exact tag or digest.
- Verified Docker run command and exposed port.
- External health and optimization evidence.
- Rollback-ready previous image reference.
- No secrets in Git history, image layers, logs, README, or CI output.

## Handoff

Give Member 4 the candidate URL/image and verification commands. Give Member 2 the frontend URL/API-base configuration if the optional UI is deployed. Give the team a short operations sheet for submission day.

