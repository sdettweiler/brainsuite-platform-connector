# Phase 18: SSE Transport - Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 4 (1 new, 3 modified)
**Analogs found:** 4 / 4 (100%)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/api/v1/endpoints/jobs.py` | endpoint | streaming | `backend/app/api/v1/endpoints/super_admin.py` | role-match |
| `backend/app/api/v1/deps.py` (new `get_current_superadmin_sse`) | dependency | request-response | `backend/app/api/v1/deps.py` lines 67–80 (`get_current_superadmin`) | exact |
| `backend/app/api/v1/__init__.py` | config | request-response | `backend/app/api/v1/__init__.py` | exact |
| `backend/app/services/sync/job_tracker.py` (add PUBLISH) | service | event-driven | `backend/app/services/sync/job_tracker.py` lines 21–106 | exact |

---

## Pattern Assignments

### `backend/app/api/v1/endpoints/jobs.py` (endpoint, streaming)

**Analog:** `backend/app/api/v1/endpoints/super_admin.py`

**Router pattern** (lines 1–41):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.api.v1.deps import get_current_superadmin

router = APIRouter()

# Pydantic models and route handlers follow
@router.get("/endpoint-name")
async def endpoint_name(
    current_user = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    # endpoint logic
    return response
```

**Key pattern notes:**
- Router is module-level: `router = APIRouter()`
- All endpoints use `Depends(get_current_superadmin)` for SuperAdmin gating
- Async def with proper imports
- HTTPException for errors with status codes

**SSE-specific patterns from RESEARCH.md:**
- Use `sse-starlette==3.4.2` (NOT yet in requirements.txt — must be added)
- `EventSourceResponse` class wraps async generator
- Session-per-operation pattern: `async with get_session_factory()() as db:` for each DB query
- Try-finally for pubsub cleanup

**Async generator yield format** (from RESEARCH.md Pattern 1, lines 200–210):
```python
yield {
    "event": "job_update",
    "data": serialize_job_event(job),  # JSON string payload
    "id": str(job.id)
}
```

---

### `backend/app/api/v1/deps.py` — Add `get_current_superadmin_sse` (dependency, request-response)

**Analog:** `backend/app/api/v1/deps.py` lines 67–80 (`get_current_superadmin`)

**Existing pattern** (lines 67–80):
```python
async def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify current user is a SuperAdmin.

    Simpler than get_current_admin -- no DB query needed, just check is_superuser flag.
    Raised when accessing platform-wide admin endpoints.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin privileges required",
        )
    return current_user
```

**New dependency: `get_current_superadmin_sse`** (D-04 from CONTEXT.md)

Core logic:
1. Extract token from `request.query_params.get("token")` (NOT Bearer header)
2. Call `decode_token(token)` from `app.core.security` (same as `get_current_user`, lines 9–26)
3. Validate token type is "access" and extract user_id from payload.get("sub")
4. Query User by UUID from DB (same as `get_current_user`, lines 37–41)
5. Check `is_superuser` flag (same as `get_current_superadmin`)

**Key imports for new dependency:**
```python
from fastapi import Request
from app.core.security import decode_token
```

**Reference implementation from RESEARCH.md Pattern 2** (lines 328–382):
```python
async def get_current_superadmin_sse(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate SuperAdmin JWT from query parameter 'token'.
    
    D-04: Read token from request.query_params["token"] instead of Bearer header.
    """
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not provided in query parameters",
        )
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin privileges required",
        )
    
    return user
```

---

### `backend/app/api/v1/__init__.py` (config, request-response)

**Analog:** `backend/app/api/v1/__init__.py` (exact match)

**Current pattern** (lines 1–13):
```python
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, platforms, dashboard, assets, scoring, brainsuite_config, super_admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(brainsuite_config.router, prefix="/brainsuite-config", tags=["brainsuite-config"])
api_router.include_router(super_admin.router, prefix="/super-admin", tags=["super-admin"])
```

**Modification required:**
1. Add `jobs` to the import line (line 2)
2. Add new `api_router.include_router()` call for jobs router with `prefix="/jobs"` and `tags=["jobs"]`

Example:
```python
from app.api.v1.endpoints import auth, users, platforms, dashboard, assets, scoring, brainsuite_config, super_admin, jobs

# ... existing routers ...
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
```

---

### `backend/app/services/sync/job_tracker.py` — Add Redis PUBLISH (service, event-driven)

**Analog:** `backend/app/services/sync/job_tracker.py` lines 21–106 (exact match)

**Current structure** (lines 1–18):
```python
"""Job tracker helpers for BackgroundJob instrumentation (Phase 17, D-16).
...
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob

logger = logging.getLogger(__name__)
```

**`create_background_job` function** (lines 21–58):
```python
async def create_background_job(
    job_type: str,
    org_id: uuid.UUID,
    platform_connection_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> uuid.UUID:
    """Insert a new BackgroundJob row with status=PENDING and return its UUID.
    
    Commits before returning so the row is visible to any background task...
    """
    async with get_session_factory()() as db:
        job = BackgroundJob(
            job_type=job_type,
            org_id=org_id,
            platform_connection_id=platform_connection_id,
            status="PENDING",
            started_at=datetime.utcnow(),
            metadata_=metadata or {},
        )
        db.add(job)
        await db.flush()
        job_id = job.id
        await db.commit()
    return job_id
```

**`update_background_job` function** (lines 61–106):
```python
async def update_background_job(
    job_id: uuid.UUID,
    status: Optional[str] = None,
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    output: Optional[dict] = None,
    error: Optional[dict] = None,
) -> None:
    """Update an existing BackgroundJob row.
    
    Automatically sets ended_at=datetime.utcnow() when status transitions
    to COMPLETE or FAILED...
    """
    async with get_session_factory()() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None:
            logger.warning("update_background_job: BackgroundJob %s not found", job_id)
            return

        if status is not None:
            job.status = status
        if progress_current is not None:
            job.progress_current = progress_current
        if progress_total is not None:
            job.progress_total = progress_total
        if output is not None:
            job.output = output
        if error is not None:
            job.error = error

        if status in ("COMPLETE", "FAILED"):
            job.ended_at = datetime.utcnow()

        db.add(job)
        await db.commit()
```

**Modification required (D-01 from CONTEXT.md):**

After each `await db.commit()` in both `create_background_job` and `update_background_job`:
1. Add `from app.core.redis import get_redis` to imports
2. Call `redis.publish("sse:job_updates", str(job_id))` after the commit
3. Wrap in try-except to prevent Redis publish failures from blocking job creation

**Pattern for adding PUBLISH:**
```python
from app.core.redis import get_redis

async def create_background_job(...) -> uuid.UUID:
    async with get_session_factory()() as db:
        job = BackgroundJob(...)
        db.add(job)
        await db.flush()
        job_id = job.id
        await db.commit()
    
    # D-01: Publish job creation event to SSE subscribers
    try:
        redis = get_redis()
        await redis.publish("sse:job_updates", str(job_id))
    except Exception as e:
        logger.warning(f"Failed to publish job update: {e}")
    
    return job_id

async def update_background_job(...) -> None:
    async with get_session_factory()() as db:
        job = await db.get(BackgroundJob, job_id)
        if job is None:
            logger.warning("...")
            return
        
        # ... update fields ...
        
        if status in ("COMPLETE", "FAILED"):
            job.ended_at = datetime.utcnow()
        
        db.add(job)
        await db.commit()
    
    # D-01: Publish job update event to SSE subscribers
    try:
        redis = get_redis()
        await redis.publish("sse:job_updates", str(job_id))
    except Exception as e:
        logger.warning(f"Failed to publish job update: {e}")
```

---

## Shared Patterns

### Authentication via Query Parameter (D-04)
**Source:** `backend/app/api/v1/deps.py` + `backend/app/core/security.py`
**Apply to:** `get_current_superadmin_sse` dependency + `jobs.py` endpoint

Core pattern (extract, decode, validate, check superuser):
```python
# Extract from query params (NOT Bearer header)
token = request.query_params.get("token")

# Decode using same function as Bearer auth
payload = decode_token(token)

# Validate token structure
if not payload or payload.get("type") != "access":
    raise HTTPException(status_code=401, detail="Invalid or expired token")

# Extract and validate user_id
user_id = payload.get("sub")
user = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))

# Check is_superuser flag
if not user.is_superuser:
    raise HTTPException(status_code=403, detail="SuperAdmin privileges required")
```

### Session-per-Operation (from Phase 17 D-14)
**Source:** `backend/app/db/base.py` + `backend/app/services/sync/job_tracker.py`
**Apply to:** `jobs.py` SSE endpoint for all DB reads

Pattern:
```python
from app.db.base import get_session_factory

async with get_session_factory()() as db:
    # Single query, immediately close session
    result = await db.execute(select(BackgroundJob).where(...))
    jobs = result.scalars().all()
# Session auto-closed here
```

Never hold a session across multiple async operations; open fresh for each DB interaction.

### Redis Connection (Singleton for Commands)
**Source:** `backend/app/core/redis.py`

Pattern:
```python
from app.core.redis import get_redis

redis = get_redis()  # Singleton async client
await redis.publish("sse:job_updates", str(job_id))
```

For SSE pubsub: create a dedicated instance via `.pubsub()` on the redis client (do NOT reuse singleton for SUBSCRIBE).

### Error Handling
**Source:** `backend/app/api/v1/endpoints/super_admin.py` + `backend/app/api/v1/deps.py`

Pattern for endpoints:
```python
from fastapi import HTTPException, status

if invalid_condition:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED or HTTP_403_FORBIDDEN,
        detail="Human-readable error message",
    )
```

Pattern for background operations (don't block on Redis failures):
```python
try:
    redis = get_redis()
    await redis.publish(...)
except Exception as e:
    logger.warning(f"Non-blocking operation failed: {e}")
    # Do NOT re-raise; job creation must not fail due to pubsub issue
```

---

## Dependencies to Install

| Package | Version | Why | Where |
|---------|---------|-----|-------|
| sse-starlette | 3.4.2 | SSE protocol framing, EventSourceResponse class, keep-alive handling | NEW dependency for jobs.py endpoint |

**Action:** Add `sse-starlette==3.4.2` to `backend/requirements.txt` before Phase 18 implementation.

---

## No Analog Found

None. All files have existing close analogs in the codebase.

---

## Metadata

**Analog search scope:** 
- `backend/app/api/v1/endpoints/` (8 endpoint files examined)
- `backend/app/api/v1/deps.py` (auth/dependency patterns)
- `backend/app/api/v1/__init__.py` (router registration)
- `backend/app/services/sync/job_tracker.py` (service instrumentation)
- `backend/app/core/security.py` (JWT decoding)
- `backend/app/core/redis.py` (Redis singleton)
- `backend/app/db/base.py` (session lifecycle)

**Files scanned:** 15+
**Pattern extraction date:** 2026-05-11
**Phase complexity:** MEDIUM (4 files, 3 existing patterns + 1 new streaming endpoint)

---

*Phase: 18-sse-transport*
*Patterns mapped: 2026-05-11*
