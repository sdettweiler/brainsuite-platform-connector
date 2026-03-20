# Phase 1: Infrastructure Portability - Research

**Researched:** 2026-03-20
**Domain:** Docker Compose, boto3/S3, MinIO, Python setup tooling, Makefile conventions
**Confidence:** HIGH

## Summary

This phase is purely infrastructure surgery: cut all Replit tentacles, replace the GCS-via-sidecar object storage with a boto3/S3 client, add Redis and MinIO as standard Compose services, and give developers a clean local-first entry point. No application feature code changes — every change is either a file replacement, an env var swap, or an addition to compose/tooling files.

The codebase already has the skeleton in place. `docker-compose.yml` has PostgreSQL, backend, and frontend. `docker-compose.dev.yml` has the hot-reload override pattern. `config.py` already has a `REDIS_URL` field (just unused). The `ObjectStorageService` class has a well-defined interface (`upload_file`, `download_blob`, `file_exists`, `served_url`, `generate_signed_url`, `get_blob_metadata`, `list_blobs`, `delete_blob`, `delete_blobs_by_prefix`) that must be preserved exactly — six callers across four sync files rely on it via `get_object_storage()`.

The single non-obvious pitfall: **MinIO's official Docker Hub images stopped being published after October 2025** when MinIO entered maintenance mode and stopped distributing free pre-built binaries. The last official tag is `RELEASE.2025-10-15T17-29-55Z` (final security release). For this project, pinning to that last known-good tag via `minio/minio:RELEASE.2025-10-15T17-29-55Z` is the recommended approach — the image remains pullable from Docker Hub at that specific tag. The alternative `alpine/minio` community image mirrors this same release.

**Primary recommendation:** Pin `minio/minio:RELEASE.2025-10-15T17-29-55Z` in docker-compose.yml; implement the boto3 S3 client with `Config(signature_version='s3v4')` for presigned URL compatibility; use stdlib `input()`/`getpass` for the setup script with no extra dependencies.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Storage backend**
- Dev: MinIO running as a Docker Compose service (S3-compatible API, no external dependencies)
- Prod: Real AWS S3
- Both dev and prod use the same boto3 client code — only `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `S3_BUCKET_NAME` env vars differ
- The existing `ObjectStorageService` (`backend/app/services/object_storage.py`) is fully replaced with a boto3-based implementation
- Full method parity required: upload, download, signed URL, list blobs, delete blob, delete by prefix — all existing methods implemented in the new service so no other code needs to change

**Dev startup experience**
- A `Makefile` at the repo root with at minimum: `make dev`, `make up` (prod mode), `make down`, `make logs`
- `make dev` detects if `.env` is missing and auto-runs the setup script before starting Docker Compose
- Dev stack: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` (hot reload for both backend and frontend) — wrapped by `make dev`

**Setup script (INFRA-08)**
- Written in Python (already a dev dependency)
- Prompts interactively for each required secret group: DB credentials, OAuth app credentials (Meta, TikTok, Google, DV360), BrainSuite API key, S3/storage config, exchange rate API key
- Auto-generates `SECRET_KEY` (32-byte hex) and `TOKEN_ENCRYPTION_KEY` (Fernet key) — shows generated values to the user before writing, user confirms
- Writes a valid `.env` file in the repo root
- Script location: `scripts/setup.py` (or `setup.py` at root — researcher to decide based on conventions)

**Redis service (INFRA-06)**
- Redis added as a standard Docker Compose service in `docker-compose.yml`
- `REDIS_URL` added to `.env.example` (value: `redis://redis:6379/0` for Docker, `redis://localhost:6379/0` for native)
- No app wiring in Phase 1 — `REDIS_URL` is already in `config.py` as an unused field; actual Redis usage (OAuth sessions) is Phase 2 work

**Replit script replacement (INFRA-03)**
- `replit_start.sh` is replaced by the Docker Compose stack — it should not be the startup path for any non-Replit deployment
- `build.sh` (Replit build script) is replaced by Docker build steps in `Dockerfile.backend` and `Dockerfile.frontend`
- Both scripts can stay in the repo for reference but should no longer be the documented startup path
- `config.py` Replit env var references (`REPLIT_DEPLOYMENT`, `REPLIT_DOMAINS`, `REPLIT_DEV_DOMAIN`) replaced with a portable `BASE_URL` env var (set explicitly in `.env.example`, defaulting to `http://localhost:8000`)

### Claude's Discretion
- MinIO version to pin in docker-compose.yml
- Exact boto3 signed URL implementation details (presigned URL TTL, expiry approach)
- Whether to add a MinIO health check in docker-compose.yml
- Makefile target names beyond the core four (`dev`, `up`, `down`, `logs`)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Application runs locally via Docker Compose with no Replit dependencies | Docker Compose service additions (Redis, MinIO); Replit env var removal from config.py, main.py, scheduler.py |
| INFRA-02 | Application deploys on any cloud provider via standard container stack | Existing Dockerfiles are already portable; Makefile `up` target wraps prod compose; no Replit-only build steps remain after replacement |
| INFRA-03 | All Replit-specific build scripts replaced with portable equivalents | `replit_start.sh` and `build.sh` superseded by Docker Compose + Makefile; both files stay in repo but are no longer documented startup paths |
| INFRA-04 | Replit object storage sidecar removed; replaced with S3-compatible storage | `ObjectStorageService` replaced with boto3 implementation; MinIO for dev, real S3 for prod; same env vars control both |
| INFRA-05 | Replit credential exchange sidecar (http://127.0.0.1:1106) removed | The GCS identity pool / sidecar token URL in `object_storage.py` is fully removed when replaced with boto3 static credentials |
| INFRA-06 | Redis runs as a standard Docker Compose service | Add `redis:7-alpine` service to `docker-compose.yml`; `REDIS_URL` env var already exists in `config.py` |
| INFRA-07 | All environment variables documented in portable `.env.example`; no Replit-specific env vars required | Extend `.env.example` with `BASE_URL`, `REDIS_URL`, S3 vars; remove `REPLIT_*` references |
| INFRA-08 | Interactive setup script that prompts for all required secrets and generates a valid `.env` | Python script at `scripts/setup.py` using stdlib `input()`/`getpass`/`secrets`/`cryptography.fernet.Fernet` |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| boto3 | 1.42.72 | AWS S3 / MinIO S3-compatible client | Official AWS SDK; works with any S3-compatible endpoint via `endpoint_url` |
| minio/minio (Docker image) | RELEASE.2025-10-15T17-29-55Z | Local S3-compatible object store | Last official stable release before project entered maintenance mode; widely cached and still pullable |
| redis (Docker image) | 7-alpine | Key-value store, OAuth session cache in Phase 2 | Official image; alpine variant keeps compose stack lean |
| botocore | (transitive with boto3) | Low-level AWS HTTP/signing | Required for `Config(signature_version='s3v4')` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cryptography | already in requirements.txt (42.0.4) | `Fernet.generate_key()` in setup script | Already a dependency; no new install needed |
| getpass (stdlib) | — | Hidden password input in setup script | For secrets and API keys that should not echo |
| secrets (stdlib) | — | `secrets.token_hex(32)` for SECRET_KEY generation | Cryptographically secure random; stdlib, no install |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `minio/minio:RELEASE.2025-10-15T17-29-55Z` | `alpine/minio:RELEASE.2025-10-15T17-29-55Z` | Same image, community mirror — viable if Docker Hub tag becomes unavailable, but adds an external registry dependency |
| `minio/minio:RELEASE.2025-10-15T17-29-55Z` | LocalStack (community) | LocalStack emulates more AWS services but is heavier (~800 MB) and overkill for S3-only dev; MinIO is simpler |
| stdlib `input()`/`getpass` for setup script | `click` or `questionary` | External dependencies; stdlib is sufficient for the linear prompt flow required here |

**Installation (additions to `backend/requirements.txt`):**
```bash
# Add boto3; remove google-cloud-storage
boto3>=1.42.72
```
Remove line: `google-cloud-storage>=2.14.0`

**Version verification (confirmed 2026-03-20):**
- `boto3`: 1.42.72 (released 2026-03-18 per PyPI) — verified via PyPI JSON API
- MinIO final tag: `RELEASE.2025-10-15T17-29-55Z` — confirmed as last published tag per GitHub releases and Docker Hub

---

## Architecture Patterns

### Recommended Project Structure (additions only)
```
brainsuite-platform-connector/
├── Makefile                          # NEW: dev/up/down/logs targets
├── scripts/
│   └── setup.py                      # NEW: interactive .env generator
├── docker-compose.yml                # EXTEND: add redis + minio services
├── docker-compose.dev.yml            # EXTEND: add minio dev overrides if needed
├── .env.example                      # EXTEND: add BASE_URL, REDIS_URL, S3 vars; remove REPLIT_*
└── backend/
    ├── requirements.txt              # CHANGE: swap google-cloud-storage for boto3
    └── app/
        ├── core/
        │   └── config.py             # CHANGE: replace _get_base_url() Replit logic with BASE_URL env var
        ├── main.py                   # CHANGE: remove REPLIT_DEPLOYMENT guard (line 80)
        └── services/
            └── object_storage.py     # REPLACE: full boto3 implementation
```

### Pattern 1: boto3 S3 Client with S3-Compatible Endpoint

**What:** Create a single boto3 S3 client configured with `endpoint_url` (for MinIO in dev) and `Config(signature_version='s3v4')`. In prod, omit `endpoint_url` and boto3 routes to real AWS S3.

**When to use:** All object storage operations — upload, download, head, list, delete, presigned URL.

**Example:**
```python
# Source: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
import boto3
from botocore.config import Config

def _make_s3_client():
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION or "us-east-1",
        "config": Config(signature_version="s3v4"),
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)
```

**Critical detail:** `Config(signature_version='s3v4')` is required. Without it, boto3 may default to SigV2 for presigned URLs, which MinIO rejects and which is deprecated on real S3. This is a common silent failure mode.

### Pattern 2: Docker Compose Service Addition

**What:** New services follow the existing pattern: image, container_name, restart, depends_on with health condition, environment, ports, volumes, healthcheck.

**Example:**
```yaml
# Source: docker-compose.yml existing service pattern
  redis:
    image: redis:7-alpine
    container_name: brainsuite_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2025-10-15T17-29-55Z
    container_name: brainsuite_minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${AWS_ACCESS_KEY_ID:-minioadmin}
      MINIO_ROOT_PASSWORD: ${AWS_SECRET_ACCESS_KEY:-minioadmin123}
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # Console (dev convenience)
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 15s
      timeout: 5s
      retries: 5
```

**Note:** MinIO healthcheck using `mc ready local` is available in the full MinIO image. An alternative is `curl -f http://localhost:9000/minio/health/live`. Recommend the curl variant as it has no dependency on the `mc` binary being in PATH within the container — verify during implementation.

### Pattern 3: Makefile with .env Guard

**What:** `make dev` checks for `.env` before calling docker compose, auto-runs setup if absent.

**Example:**
```makefile
# Source: community convention, verified against multiple Makefile examples
.PHONY: dev up down logs setup

dev:
	@if [ ! -f .env ]; then \
		echo "No .env found — running setup..."; \
		python3 scripts/setup.py; \
	fi
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

up:
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f
```

### Pattern 4: BASE_URL Replacement in config.py

**What:** Replace `_get_base_url()` Replit logic with a simple env var read.

**Example:**
```python
# Replace the entire _get_base_url() function with:
class Settings(BaseSettings):
    BASE_URL: str = "http://localhost:8000"

    def get_base_url(self) -> str:
        return self.BASE_URL
```

The three callers of `get_base_url()` / `get_redirect_uri()` in `config.py` remain unchanged — only the implementation of `get_base_url()` changes.

### Pattern 5: ObjectStorageService Method Parity Map

The new boto3 implementation must provide every method callers currently use:

| Current method | boto3 equivalent | Notes |
|----------------|-----------------|-------|
| `upload_file(local_path, relative_path, content_type)` | `s3.upload_file()` with `ExtraArgs={'ContentType': ct}` | Returns `served_url(relative_path)` (no change in return value) |
| `file_exists(relative_path)` | `s3.head_object()` in try/except `ClientError` | Returns bool |
| `download_blob(relative_path)` | `s3.get_object()` → `Body.read()` | Returns `(bytes, content_type)` tuple |
| `get_blob_metadata(relative_path)` | `s3.head_object()` | Returns `{"content_type": ..., "size": ...}` dict |
| `generate_signed_url(relative_path, ttl_sec)` | `s3.generate_presigned_url('get_object', ...)` | Must use `s3v4` config |
| `delete_blob(relative_path)` | `s3.delete_object()` | Returns bool |
| `list_blobs(prefix)` | `s3.list_objects_v2(Prefix=...)` paginator | Returns list of relative paths |
| `delete_blobs_by_prefix(prefix)` | calls `list_blobs` then `delete_blob` | Unchanged delegation pattern |
| `served_url(relative_path)` | `/objects/{relative_path}` | No change — same as current implementation |

**Key insight:** `served_url()` returns the backend-proxied path, not a direct S3 URL. This path is used in `main.py` for serving assets. The boto3 presigned URL is separate and used by the BrainSuite scoring service in Phase 3 — in Phase 1 it just needs to work.

### Anti-Patterns to Avoid

- **Using `latest` MinIO tag:** `minio/minio:latest` no longer resolves to a maintained build. Pin to `RELEASE.2025-10-15T17-29-55Z` explicitly.
- **Omitting `Config(signature_version='s3v4')`:** Presigned URLs will fail with `SignatureDoesNotMatch` against MinIO — silent in some configurations.
- **Leaving `google-cloud-storage` in requirements.txt:** Docker image build will install GCS libraries even though no code imports them; adds ~50 MB to the image and is a misleading dependency.
- **Using `REPLIT_DEPLOYMENT` as a production guard:** `main.py` line 80 uses `REPLIT_DEPLOYMENT` to add a 15s startup delay for scheduler. This should be replaced with a generic `DEPLOYMENT_ENVIRONMENT` or similar env var check.
- **Hardcoding MinIO bucket auto-creation in compose:** MinIO does not auto-create buckets. The dev setup script (or a MinIO init container) must create the bucket. Recommend the setup script creates the bucket via boto3 after writing `.env`, or document in `.env.example` that the bucket must be created manually.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Presigned S3 URL generation | Custom HMAC-SHA256 signing | `boto3.generate_presigned_url()` | AWS signing protocol has edge cases (path normalization, chunked encoding); boto3 handles all of them |
| S3-compatible multipart upload | Custom chunked HTTP | `boto3.upload_file()` (auto-multipart for large files) | boto3 handles multipart threshold automatically |
| Secret key generation | Custom random string | `secrets.token_hex(32)` (stdlib) | Cryptographically secure; no dependencies |
| Fernet key generation | Custom base64 encoding | `cryptography.fernet.Fernet.generate_key()` | Ensures correct key format and length that Fernet validation (Phase 2 SEC-03) expects |
| Redis health check in compose | Custom TCP probe | `redis-cli ping` command check | Official pattern; zero custom code |

---

## Common Pitfalls

### Pitfall 1: MinIO Presigned URLs Fail with Signature Error

**What goes wrong:** `generate_presigned_url` produces a URL that returns 403/`SignatureDoesNotMatch` when accessed via MinIO.
**Why it happens:** boto3 defaults to SigV2 for presigned URLs in some configurations. MinIO requires SigV4.
**How to avoid:** Always create the boto3 S3 client with `config=Config(signature_version='s3v4')`.
**Warning signs:** 403 response with XML body containing `<Code>SignatureDoesNotMatch</Code>`.

### Pitfall 2: MinIO Bucket Not Pre-Created

**What goes wrong:** First `upload_file` call after `docker compose up` fails with `NoSuchBucket`.
**Why it happens:** MinIO does not auto-create buckets on first use; unlike some object stores, it requires explicit bucket creation.
**How to avoid:** The setup script should call `s3.create_bucket(Bucket=bucket_name)` (or `head_bucket` + `create_bucket` if not exists) immediately after writing `.env`. Document this clearly.
**Warning signs:** `NoSuchBucket` ClientError on first upload attempt.

### Pitfall 3: `served_url()` vs Presigned URL Confusion

**What goes wrong:** Code that currently works (asset serving via `/objects/...` proxy endpoint) breaks because a developer confuses the `served_url()` return with a presigned URL.
**Why it happens:** The existing `ObjectStorageService` has two URL concepts: `served_url()` (a relative path through the FastAPI static proxy) and `generate_signed_url()` (a direct S3 presigned URL). They serve different purposes.
**How to avoid:** Keep `served_url()` returning `/objects/{relative_path}` exactly as today. Presigned URLs from boto3 use the `S3_ENDPOINT_URL` so they point to `localhost:9000` in dev — only valid for internal use or BrainSuite API requests.
**Warning signs:** Frontend showing broken images or direct S3 URLs leaking into `asset_url` DB columns.

### Pitfall 4: google-cloud-storage Import at Module Level

**What goes wrong:** Docker image build fails or import error occurs at startup even after replacing `object_storage.py`, because `google-cloud-storage` is still in `requirements.txt` and gets imported elsewhere.
**Why it happens:** `object_storage.py` has top-level `from google.cloud import storage` import. After replacement, that import is gone — but `requirements.txt` must be cleaned up too.
**How to avoid:** Remove `google-cloud-storage>=2.14.0` from `requirements.txt` when replacing `object_storage.py`.
**Warning signs:** Build succeeds but image is ~50 MB larger than expected; `google.cloud` namespace available in container.

### Pitfall 5: Replit Scheduler Keep-Alive Ping Still Active

**What goes wrong:** `scheduler.py` adds a `_keep_alive_ping` job when `REPLIT_DEPLOYMENT == "1"`. If this env var is set in any non-Replit deploy, it will ping `https://{REPLIT_DOMAINS}/health` (which is empty/invalid).
**Why it happens:** Three files still read `REPLIT_DEPLOYMENT` or `REPLIT_DOMAINS`: `config.py`, `main.py`, `scheduler.py`.
**How to avoid:** Remove all three `REPLIT_*` reads as part of INFRA-01/INFRA-03. The keep-alive ping function has no equivalent in a non-Replit deployment and should simply be removed.
**Warning signs:** Scheduler logs showing repeated connection errors to `https://undefined/health`.

### Pitfall 6: MinIO Presigned URL Uses Internal Docker Hostname

**What goes wrong:** Presigned URLs generated by the backend contain `http://minio:9000/...` (the Docker network hostname), which browsers cannot resolve.
**Why it happens:** boto3 uses whatever `endpoint_url` is configured. Inside Docker, this is `http://minio:9000`. The presigned URL is opaque to boto3 — it bakes in the endpoint host.
**How to avoid:** For Phase 1, presigned URLs are only used internally (the backend generates them for its own requests or for BrainSuite in Phase 3). Assets served to the browser go through the `/objects/...` proxy endpoint, not presigned URLs. Acknowledge this limitation in `.env.example` comments. When public presigned URLs are needed (Phase 3), `S3_PUBLIC_ENDPOINT_URL` (pointing to `localhost:9000` or a real domain) will be required.
**Warning signs:** Presigned URL returned by API contains `minio:9000` hostname.

---

## Code Examples

Verified patterns from official sources:

### boto3 S3 Client (Dev/Prod Unified)
```python
# Source: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

def _make_s3_client(endpoint_url: str | None, access_key: str, secret_key: str, region: str = "us-east-1"):
    kwargs = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "region_name": region,
        "config": Config(signature_version="s3v4"),
    }
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("s3", **kwargs)
```

### Presigned URL Generation
```python
# Source: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_url.html
def generate_signed_url(self, relative_path: str, ttl_sec: int = 3600) -> Optional[str]:
    object_name = self._object_name(relative_path)
    try:
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": object_name},
            ExpiresIn=ttl_sec,
        )
        return url
    except ClientError as e:
        logger.warning(f"Signed URL generation failed: {e}")
        return None
```

### file_exists via head_object
```python
# Source: boto3 docs pattern; ClientError code check is the standard idiom
from botocore.exceptions import ClientError

def file_exists(self, relative_path: str) -> bool:
    try:
        self._client.head_object(Bucket=self._bucket_name, Key=self._object_name(relative_path))
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
```

### Interactive Setup Script Structure
```python
# Source: Python stdlib conventions; no external dependencies
import getpass, secrets, sys
from pathlib import Path
from cryptography.fernet import Fernet

def prompt(label: str, default: str = "", secret: bool = False) -> str:
    full_label = f"{label} [{default}]: " if default else f"{label}: "
    if secret:
        value = getpass.getpass(full_label)
    else:
        value = input(full_label)
    return value.strip() or default

def main():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        confirm = input(f".env already exists at {env_path}. Overwrite? [y/N]: ")
        if confirm.lower() != "y":
            sys.exit(0)
    # ... prompt groups ...
    secret_key = secrets.token_hex(32)
    fernet_key = Fernet.generate_key().decode()
    print(f"\nGenerated SECRET_KEY:          {secret_key}")
    print(f"Generated TOKEN_ENCRYPTION_KEY: {fernet_key}")
    confirm = input("\nWrite these values to .env? [Y/n]: ")
    if confirm.lower() == "n":
        sys.exit(0)
    # ... write .env ...
```

### MinIO Docker Compose Service (healthcheck)
```yaml
# Source: docker-compose.yml existing healthcheck pattern; MinIO health endpoint docs
  minio:
    image: minio/minio:RELEASE.2025-10-15T17-29-55Z
    container_name: brainsuite_minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${AWS_ACCESS_KEY_ID:-minioadmin}
      MINIO_ROOT_PASSWORD: ${AWS_SECRET_ACCESS_KEY:-minioadmin123}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5
```

### Redis Docker Compose Service
```yaml
# Source: docker-compose.yml existing pattern; Redis official docs
  redis:
    image: redis:7-alpine
    container_name: brainsuite_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MinIO via official Docker Hub | MinIO via pinned tag or `alpine/minio` community image | Oct 2025 — MinIO stopped publishing free binaries | Must pin specific tag; do not use `latest` |
| GCS `identity_pool.Credentials` via Replit sidecar | boto3 static credentials via env vars | This phase | Eliminates sidecar dependency entirely |
| `secrets.token_urlsafe(32)` for SECRET_KEY | `secrets.token_hex(32)` | No change — both work; `token_hex` is more conventional for 32-byte hex keys | Minor |

**Deprecated/outdated in this codebase:**
- `google-cloud-storage>=2.14.0` in requirements.txt: Remove when replacing `object_storage.py`
- `REPLIT_DEPLOYMENT`, `REPLIT_DOMAINS`, `REPLIT_DEV_DOMAIN` env vars: Remove from `config.py`, `main.py`, `scheduler.py`
- `REPLIT_SIDECAR_ENDPOINT` constant in `object_storage.py`: Removed when file is replaced
- `DEFAULT_OBJECT_STORAGE_BUCKET_ID` and `PUBLIC_OBJECT_SEARCH_PATHS` env vars: Replaced by `S3_BUCKET_NAME`
- `_keep_alive_ping()` function in `scheduler.py`: Replit-specific; remove entirely

---

## Open Questions

1. **MinIO bucket auto-creation responsibility**
   - What we know: MinIO requires explicit bucket creation; boto3's `create_bucket()` works against MinIO
   - What's unclear: Should the setup script create the bucket via boto3 (requires MinIO to be running), or should there be a `docker compose exec` initialization step, or should the `ObjectStorageService.__init__` create the bucket lazily?
   - Recommendation: Have the setup script write `.env`, then print instructions to run `make dev` which starts MinIO, then prompt "Press Enter when MinIO is ready to create bucket..." and call `create_bucket`. Alternatively, add a `make init-storage` Makefile target that creates the bucket once Compose is up.

2. **Presigned URLs with internal Docker hostname**
   - What we know: In Phase 1, `generate_signed_url()` is called only from `main.py`'s `/objects/{path}` handler (internally). Phase 3 will use presigned URLs for BrainSuite API.
   - What's unclear: Whether Phase 1 needs `S3_PUBLIC_ENDPOINT_URL` (external-facing) as a separate var, or if this can wait for Phase 3.
   - Recommendation: Phase 1 only needs internal presigned URL functionality. Add a comment in `.env.example` noting that `S3_ENDPOINT_URL` is the internal Docker endpoint; document the public URL limitation for Phase 3 planning.

3. **`DEPLOYMENT_ENVIRONMENT` replacement for `REPLIT_DEPLOYMENT`**
   - What we know: `main.py` uses `REPLIT_DEPLOYMENT == "1"` to add a 15s startup delay for the scheduler in production. This is a real need for cloud deployments.
   - What's unclear: Whether to introduce a new `DEPLOYMENT_ENVIRONMENT=production` env var or simply remove the delay entirely.
   - Recommendation: Replace with `SCHEDULER_STARTUP_DELAY_SECONDS` env var defaulting to `0`; set to `15` in prod `.env`. This is more explicit than a boolean flag.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected in current codebase |
| Config file | None — Wave 0 must create |
| Quick run command | `pytest backend/tests/ -x -q` (after Wave 0 setup) |
| Full suite command | `pytest backend/tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Docker Compose stack starts with no Replit env vars set | smoke | `docker compose config` validates; `docker compose up --dry-run` (manual) | ❌ Wave 0 |
| INFRA-04 | `ObjectStorageService` upload/download/exists/delete work against MinIO | unit (with moto or mock) | `pytest backend/tests/test_object_storage.py -x` | ❌ Wave 0 |
| INFRA-04 | `generate_signed_url` returns a non-None URL string | unit | `pytest backend/tests/test_object_storage.py::test_generate_signed_url -x` | ❌ Wave 0 |
| INFRA-05 | No `127.0.0.1:1106` connection attempt on import of `object_storage` | unit | `pytest backend/tests/test_object_storage.py::test_no_sidecar_import -x` | ❌ Wave 0 |
| INFRA-07 | `.env.example` contains no `REPLIT_*` keys | static check | `grep -c REPLIT .env.example` returns 0 | ❌ Wave 0 |
| INFRA-08 | Setup script generates valid `.env` non-interactively (with stdin pipe) | unit | `pytest backend/tests/test_setup_script.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/ -x -q` (after Wave 0 installs pytest)
- **Per wave merge:** `pytest backend/tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/__init__.py` — package init
- [ ] `backend/tests/test_object_storage.py` — covers INFRA-04, INFRA-05
- [ ] `backend/tests/test_setup_script.py` — covers INFRA-08
- [ ] `pytest` + `moto[s3]` added to dev dependencies or test requirements

**Note on INFRA-01/INFRA-02/INFRA-06/INFRA-07:** These are primarily verified by inspection (compose file diff, `.env.example` diff, `grep` for REPLIT vars) rather than automated tests. The planner should include explicit verification steps rather than test code for these.

---

## Sources

### Primary (HIGH confidence)
- PyPI JSON API `https://pypi.org/pypi/boto3/json` — version 1.42.72 confirmed 2026-03-20
- Docker Hub `hub.docker.com/r/minio/minio` + GitHub `github.com/minio/minio/releases` — last tag `RELEASE.2025-10-15T17-29-55Z` confirmed
- `boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html` — presigned URL + `s3v4` config requirement
- Direct code inspection of `backend/app/services/object_storage.py`, `config.py`, `main.py`, `scheduler.py`, `docker-compose.yml`, `docker-compose.dev.yml`

### Secondary (MEDIUM confidence)
- `github.com/boto/boto3/issues/4598` — confirmed `Config(signature_version='s3v4')` recommendation for presigned URLs
- `rmoff.net/2026/01/14/alternatives-to-minio-for-single-node-local-s3/` — MinIO maintenance mode context
- `medium.com/towardsdev/minio-latest-security-release-now-available-as-alpine-minio-docker-image` — `alpine/minio` as community mirror

### Tertiary (LOW confidence)
- None — all critical claims verified against primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — boto3 version verified via PyPI API; MinIO tag verified via Docker Hub/GitHub; existing compose pattern inspected directly
- Architecture: HIGH — based on direct code inspection of all affected files
- Pitfalls: HIGH for boto3/MinIO-specific items (verified against GitHub issues and official docs); MEDIUM for MinIO bucket creation (behavioral, tested conceptually but not in this environment)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (boto3 releases frequently; MinIO tag is pinned so stable)
