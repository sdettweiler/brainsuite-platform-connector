# Phase 1: Infrastructure Portability - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Decouple the application from Replit so it runs fully outside Replit: local dev via Docker Compose and deployable to any cloud provider via standard container tooling. This phase replaces all Replit-specific sidecars, scripts, and env vars. No application feature work — purely infrastructure and developer tooling.

</domain>

<decisions>
## Implementation Decisions

### Storage backend
- **Dev:** MinIO running as a Docker Compose service (S3-compatible API, no external dependencies)
- **Prod:** Real AWS S3
- Both dev and prod use the same boto3 client code — only `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `S3_BUCKET_NAME` env vars differ
- The existing `ObjectStorageService` (`backend/app/services/object_storage.py`) is fully replaced with a boto3-based implementation
- **Full method parity required:** upload, download, signed URL, list blobs, delete blob, delete by prefix — all existing methods implemented in the new service so no other code needs to change

### Dev startup experience
- A `Makefile` at the repo root with at minimum: `make dev`, `make up` (prod mode), `make down`, `make logs`
- `make dev` detects if `.env` is missing and auto-runs the setup script before starting Docker Compose
- Dev stack: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` (hot reload for both backend and frontend) — wrapped by `make dev`

### Setup script (INFRA-08)
- Written in Python (already a dev dependency)
- Prompts interactively for each required secret group: DB credentials, OAuth app credentials (Meta, TikTok, Google, DV360), BrainSuite API key, S3/storage config, exchange rate API key
- Auto-generates `SECRET_KEY` (32-byte hex) and `TOKEN_ENCRYPTION_KEY` (Fernet key) — shows generated values to the user before writing, user confirms
- Writes a valid `.env` file in the repo root
- Script location: `scripts/setup.py` (or `setup.py` at root — researcher to decide based on conventions)

### Redis service (INFRA-06)
- Redis added as a standard Docker Compose service in `docker-compose.yml`
- `REDIS_URL` added to `.env.example` (value: `redis://redis:6379/0` for Docker, `redis://localhost:6379/0` for native)
- **No app wiring in Phase 1** — `REDIS_URL` is already in `config.py` as an unused field; actual Redis usage (OAuth sessions) is Phase 2 work

### Replit script replacement (INFRA-03)
- `replit_start.sh` is replaced by the Docker Compose stack — it should not be the startup path for any non-Replit deployment
- `build.sh` (Replit build script) is replaced by Docker build steps in `Dockerfile.backend` and `Dockerfile.frontend`
- Both scripts can stay in the repo for reference but should no longer be the documented startup path
- `config.py` Replit env var references (`REPLIT_DEPLOYMENT`, `REPLIT_DOMAINS`, `REPLIT_DEV_DOMAIN`) replaced with a portable `BASE_URL` env var (set explicitly in `.env.example`, defaulting to `http://localhost:8000`)

### Claude's Discretion
- MinIO version to pin in docker-compose.yml
- Exact boto3 signed URL implementation details (presigned URL TTL, expiry approach)
- Whether to add a MinIO health check in docker-compose.yml
- Makefile target names beyond the core four (`dev`, `up`, `down`, `logs`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` §Infrastructure & Portability — INFRA-01 through INFRA-08: full requirement list for this phase
- `.planning/ROADMAP.md` §Phase 1 — Success criteria (5 items) that define done

### Existing code to replace
- `backend/app/services/object_storage.py` — the Replit-sidecar-based GCS service being fully replaced
- `backend/app/core/config.py` — contains Replit env var references (`REPLIT_DEPLOYMENT`, `REPLIT_DOMAINS`, `REPLIT_DEV_DOMAIN`) to be replaced
- `replit_start.sh` — Replit startup script being superseded
- `build.sh` — Replit build script being superseded

### Existing Docker infrastructure (extend, don't rewrite)
- `docker-compose.yml` — existing compose file; add Redis + MinIO services
- `docker-compose.dev.yml` — existing dev override; extend if needed
- `docker/Dockerfile.backend` — existing backend Dockerfile
- `docker/Dockerfile.frontend` — existing prod frontend Dockerfile
- `docker/Dockerfile.frontend.dev` — existing dev frontend Dockerfile

### Environment documentation
- `.env.example` — existing partial example; extend with Redis, S3/MinIO, and remove Replit-specific vars

No external API specs — all requirements are captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml`: PostgreSQL + backend + frontend already defined; add Redis + MinIO as additional services
- `docker-compose.dev.yml`: hot reload pattern already established (backend: uvicorn --reload, frontend: dev server with volume mount)
- `docker/Dockerfile.backend`: Python 3.11-slim, pip install, alembic upgrade head + uvicorn start — no changes needed unless boto3 added to requirements.txt
- `backend/app/core/config.py`: `REDIS_URL` field already exists (just unused); `Settings.get_base_url()` is the method to update

### Established Patterns
- Docker Compose services follow: image/build, container_name, restart, depends_on (with health condition), environment, ports, volumes, healthcheck pattern — new services should follow this
- Backend config uses `pydantic_settings.BaseSettings` with `.env` file — new env vars added as Optional fields with defaults
- Object storage is accessed via a singleton `get_object_storage()` function — new implementation keeps this interface so callers don't change

### Integration Points
- `backend/app/services/object_storage.py` → all sync services import `get_object_storage()` — full method parity means zero changes in sync services
- `backend/app/core/config.py` → `_get_base_url()` reads Replit env vars; replace with `BASE_URL` env var
- `docker-compose.yml` → add `redis` and `minio` services; update `backend` service environment to include `REDIS_URL` and S3 vars

</code_context>

<specifics>
## Specific Ideas

No specific product references — this is infrastructure work. Open to standard approaches for Makefile conventions, MinIO setup, and boto3 S3 patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-infrastructure-portability*
*Context gathered: 2026-03-20*
