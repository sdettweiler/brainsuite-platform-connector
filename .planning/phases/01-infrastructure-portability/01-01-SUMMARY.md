---
phase: 01-infrastructure-portability
plan: 01
subsystem: infra
tags: [docker-compose, redis, minio, s3, boto3, python, fastapi]

requires: []

provides:
  - Redis service in Docker Compose (brainsuite_redis, redis:7-alpine)
  - MinIO service in Docker Compose (brainsuite_minio, RELEASE.2025-10-15T17-29-55Z)
  - Portable .env.example with BASE_URL, REDIS_URL, S3_ENDPOINT_URL, S3_BUCKET_NAME, AWS_* vars
  - config.py BASE_URL env var replacing Replit domain logic
  - S3/MinIO fields in Settings (S3_ENDPOINT_URL, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
  - SCHEDULER_STARTUP_DELAY_SECONDS replacing REPLIT_DEPLOYMENT guard in main.py
  - Replit-free scheduler.py (no _keep_alive_ping, no keep_alive job)
  - boto3>=1.42.0 in requirements.txt (replaces google-cloud-storage)

affects:
  - 01-02 (object storage service replacement uses boto3 and S3 config fields)
  - 01-03 (Makefile and setup script reference .env.example vars and compose services)

tech-stack:
  added:
    - boto3>=1.42.0
  patterns:
    - Docker Compose services follow: image, container_name, restart, depends_on with health condition, environment, ports, volumes, healthcheck
    - Backend service depends_on includes service_healthy conditions for db, redis, minio
    - Env vars use ${VAR_NAME:-default} pattern for all compose environment blocks
    - config.py Settings fields mirror .env.example vars exactly

key-files:
  created: []
  modified:
    - docker-compose.yml
    - .env.example
    - backend/app/core/config.py
    - backend/app/main.py
    - backend/app/services/sync/scheduler.py
    - backend/requirements.txt

key-decisions:
  - "Pin MinIO to RELEASE.2025-10-15T17-29-55Z — last official tag before project entered maintenance mode in Oct 2025"
  - "Use curl-based healthcheck for MinIO (http://localhost:9000/minio/health/live) — no mc binary dependency"
  - "SCHEDULER_STARTUP_DELAY_SECONDS defaults to 0; set to 15 in production .env — more explicit than boolean flag"
  - "FRONTEND_URL defaults to http://localhost:8000 (same as BASE_URL) — both set via .env in production"

patterns-established:
  - "Pattern: All new env vars added to both docker-compose.yml backend service environment block AND .env.example with matching names"
  - "Pattern: Compose service healthchecks use CMD-SHELL with curl for HTTP services, CMD for redis-cli ping"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03, INFRA-05, INFRA-06, INFRA-07]

duration: 3min
completed: 2026-03-20
---

# Phase 01 Plan 01: Infrastructure Portability — Compose + Backend Cleanup Summary

**Redis and MinIO added as Docker Compose services with healthchecks; all REPLIT_* env var references removed from config.py, main.py, and scheduler.py; boto3 replaces google-cloud-storage in requirements.txt**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-20T15:31:54Z
- **Completed:** 2026-03-20T15:34:52Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Docker Compose stack now defines 5 services (db, redis, minio, backend, frontend) with health checks; backend waits for all three infrastructure services to be healthy before starting
- All three Replit env var read sites removed from backend Python code (`config.py` _get_base_url(), `main.py` REPLIT_DEPLOYMENT guard, `scheduler.py` _keep_alive_ping + keep_alive job)
- S3/MinIO configuration fields added to Settings class, paired with matching .env.example documentation; stack is deployable to any cloud provider without Replit dependencies

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Redis + MinIO services to Docker Compose and update .env.example** - `68e2d68` (feat)
2. **Task 2: Remove Replit references from config.py, main.py, scheduler.py and swap requirements** - `f298f03` (feat)

## Files Created/Modified

- `docker-compose.yml` - Added redis and minio services with healthchecks; updated backend depends_on and environment block with S3, Redis, BASE_URL, SCHEDULER_STARTUP_DELAY_SECONDS vars; added minio_data volume
- `.env.example` - Added BASE_URL, SCHEDULER_STARTUP_DELAY_SECONDS, REDIS_URL, S3_ENDPOINT_URL, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION sections; zero REPLIT_* references
- `backend/app/core/config.py` - Removed _get_base_url() function and import os; added BASE_URL, S3_ENDPOINT_URL, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, SCHEDULER_STARTUP_DELAY_SECONDS fields; get_base_url() now returns self.BASE_URL
- `backend/app/main.py` - Replaced REPLIT_DEPLOYMENT check with SCHEDULER_STARTUP_DELAY_SECONDS env var read
- `backend/app/services/sync/scheduler.py` - Removed _keep_alive_ping() function entirely; removed keep_alive job registration block from startup_scheduler()
- `backend/requirements.txt` - Swapped google-cloud-storage>=2.14.0 for boto3>=1.42.0

## Decisions Made

- Pinned MinIO to `RELEASE.2025-10-15T17-29-55Z` — the last official tag before MinIO stopped publishing free binaries in October 2025; still pullable from Docker Hub at that specific tag
- Used curl-based MinIO healthcheck (`http://localhost:9000/minio/health/live`) rather than `mc ready local` to avoid dependency on the mc binary being in PATH inside the container
- Replaced boolean `REPLIT_DEPLOYMENT == "1"` guard with numeric `SCHEDULER_STARTUP_DELAY_SECONDS` — more explicit for production tuning (set to 15 in production .env)
- FRONTEND_URL in config.py defaults to `http://localhost:8000` (same as BASE_URL); in production both are set via .env

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `docker compose --quiet` flag is not available in this environment's Docker version; verified compose YAML syntax via Python's `yaml.safe_load()` instead — YAML parses cleanly.

## User Setup Required

None — no external service configuration required for this plan. MinIO and Redis start automatically via `docker compose up`.

## Next Phase Readiness

- Plan 01-02 (ObjectStorageService boto3 replacement) can proceed: boto3 is in requirements.txt, S3 config fields are in Settings, MinIO service is defined in compose
- Plan 01-03 (Makefile + setup script) can proceed: .env.example documents all required vars, compose stack is defined
- Phase 2 (Security hardening) unblocked from infrastructure perspective: no Replit env vars remain, stack is portable

---
*Phase: 01-infrastructure-portability*
*Completed: 2026-03-20*
