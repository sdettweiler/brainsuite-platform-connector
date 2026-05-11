# Phase 18: SSE Transport - Research

**Researched:** 2026-05-11
**Domain:** Real-time streaming transport, async Redis pub/sub, FastAPI lifecycle management
**Confidence:** HIGH

## Summary

Phase 18 implements a FastAPI Server-Sent Events (SSE) streaming endpoint that pushes real-time job updates to connected SuperAdmin browsers. The implementation sits atop Phase 17's instrumented BackgroundJob records and leverages Redis PUBLISH/SUBSCRIBE as the notification bus.

This research confirms:
1. **sse-starlette 3.4.2 is production-ready** as the approved package (released May 6, 2026, current as of research date). The EventSourceResponse class handles SSE protocol framing, keep-alive headers, and async generator integration natively [VERIFIED: pypi.org/project/sse-starlette].
2. **redis-py 5.0.0+ supports both patterns needed**: singleton client for Redis command operations (PUBLISH), and dedicated pubsub connections for SUBSCRIBE. A fresh `redis.from_url()` instance can be created per SSE client without connection pool conflicts [CITED: redis.readthedocs.io/en/stable/examples/asyncio_examples.html].
3. **request.is_disconnected() is reliable and expected in async generators** when paired with try-finally blocks and asyncio.sleep polling loops. FastAPI 0.115.0 with Starlette 0.45+ has no known blocking issues for the patterns required here [CITED: github.com/fastapi/fastapi discussions and documentation].
4. **Connection leak prevention depends on explicit pubsub cleanup**, not just context managers. The pattern `async with r.pubsub() as pubsub:` + `finally: await pubsub.unsubscribe()` guarantees cleanup even on unexpected disconnects [CITED: redis.readthedocs.io asyncio examples].
5. **JWT query parameter auth is an acceptable tradeoff** for an internal SuperAdmin-only endpoint — all major auth patterns from Phase 2 (get_current_user, decode_token) apply directly and can be adapted for query param input [VERIFIED: codebase review of backend/app/api/v1/deps.py and backend/app/core/security.py].

**Primary recommendation:** Implement the SSE endpoint using sse-starlette's EventSourceResponse, wrap the async generator in try-finally blocks, and always create a dedicated Redis pubsub connection per client (not reusing the singleton client).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 through D-03:** Redis PUBLISH/SUBSCRIBE as the notification bus (not polling, not Kafka)
- **D-04:** JWT via query parameter for auth (not Bearer header, not cookies)
- **D-05 through D-10:** Global firehose, minimal event payload, 24h burst on connect, 30-second heartbeat, request.is_disconnected() for disconnect detection

### Claude's Discretion
- Token delivery (D-04) is confirmed as user's pragmatic choice for an internal SuperAdmin tool

### Deferred Ideas (OUT OF SCOPE)
- Redis pub/sub scaling (SSE-03) — future v1.4 concern at 50+ concurrent SuperAdmins
- Last-Event-ID reconnect support — initial 24h burst sufficient
- GET /jobs and GET /jobs/{id} REST endpoints — Phase 19 scope

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SSE-01 | Backend exposes SSE endpoint streaming job updates to SuperAdmin clients in real time | sse-starlette EventSourceResponse + redis pubsub pattern confirmed; async generator yields job_update events; context7 and redis-py docs provide implementation templates |
| SSE-02 | SSE connections include keepalive heartbeats and are cleaned up on disconnect | 30-second ping/heartbeat supported by EventSourceResponse; request.is_disconnected() polling with try-finally cleanup prevents Uvicorn worker exhaustion |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE streaming endpoint | API / Backend | — | FastAPI router exposes GET /api/v1/jobs/stream; handles connection lifecycle and event generation |
| Redis pub/sub subscription | API / Backend | — | SSE async generator maintains dedicated pubsub connection per client; subscribes to sse:job_updates channel |
| Job update publishing | API / Backend | — | job_tracker.py's update_background_job helper calls PUBLISH after DB write (Phase 17 PUBLISH calls, not Phase 18 scope) |
| Client disconnect detection | API / Backend | — | request.is_disconnected() polling in async generator loop ensures timely cleanup |
| Token validation | API / Backend | — | get_current_superadmin_sse dependency validates JWT from query param, replicates decode_token from auth.py |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | 3.4.2 | Production SSE streaming for Starlette/FastAPI | Released May 6, 2026; W3C spec-compliant; native async/await; auto-disconnect detection; approved by D-04 |
| redis-py (asyncio) | >=5.0.0 | Async Redis client for pub/sub and command operations | Current project dependency; supports both singleton commands and dedicated pubsub connections; actively maintained |
| FastAPI | 0.115.0 | HTTP framework with async generator streaming support | Current project dependency; Request.is_disconnected() reliable; StreamingResponse + EventSourceResponse both supported |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | Built-in | Async loop management, sleep/polling, CancelledError handling | Default in all async generators; required for 30-second heartbeat loop |
| uvicorn | 0.24.0 | ASGI server running FastAPI app | Current deployment; handles streaming responses; requires pool tuning for concurrent SSE connections (future concern) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette EventSourceResponse | FastAPI StreamingResponse (raw) | More boilerplate; manual SSE frame formatting; would need to replicate ping logic, Content-Type headers, event parsing |
| Redis pub/sub | Polling the DB directly in loop | No network latency for subscription message; but requires constant SELECT queries per client; scales worse at 50+ SuperAdmins |
| query parameter JWT | Bearer header + custom EventSource client | EventSource is standard browser API; does not support custom headers; Bearer would require custom JS wrapper (fragile) |

**Installation:**
```bash
pip install sse-starlette==3.4.2
```

**Version verification:** sse-starlette 3.4.2 is confirmed current as of May 6, 2026 [VERIFIED: pypi.org/project/sse-starlette]. redis-py >=5.0.0 is already in requirements.txt. FastAPI 0.115.0 is already in requirements.txt.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────┐
│  SuperAdmin Browser                 │
│  EventSource("/api/v1/jobs/stream?  │
│   token=<access_jwt>")              │
└─────────────┬───────────────────────┘
              │ HTTP/1.1 upgrade to
              │ text/event-stream
              │
┌─────────────▼───────────────────────┐
│  FastAPI SSE Endpoint               │
│  (GET /api/v1/jobs/stream)          │
├─────────────────────────────────────┤
│ 1. Validate JWT from query param    │
│ 2. Create Redis pubsub connection   │
│ 3. On connect: fetch 24h job burst  │
│ 4. Subscribe to sse:job_updates     │
│ 5. Enter async generator loop:      │
│    - Check request.is_disconnected()│
│    - Yield keepalive ping every 30s │
│    - On pubsub message: fetch job + │
│      yield job_update event         │
│ 6. Finally: cleanup pubsub conn     │
└─────────────┬───────────────────────┘
              │ PUBLISH sse:job_updates
              │ (notification signal)
              │
┌─────────────▼───────────────────────┐
│  Redis Pub/Sub Bus                  │
│  Channel: sse:job_updates           │
└─────────────┬───────────────────────┘
              │ Receives message from
              │ job_tracker.py
              │
┌─────────────▼───────────────────────┐
│  Job Tracker & PostgreSQL           │
│  (Phase 17 instrumentation)         │
│  - create_background_job() calls    │
│    PUBLISH sse:job_updates <uuid>   │
│  - update_background_job() calls    │
│    PUBLISH sse:job_updates <uuid>   │
└─────────────────────────────────────┘
```

**Data flow:**
1. Service (sync/download/autofill/scoring) calls job_tracker.update_background_job(job_id)
2. job_tracker PUBLISH's job_id to Redis sse:job_updates channel
3. SSE generator's pubsub.get_message() receives the notification (job_id string)
4. SSE generator queries BackgroundJob by job_id, serializes D-06 payload, yields event
5. EventSourceResponse encodes event with SSE framing, streams to browser
6. Browser EventSource fires `message` or `job_update` event, Phase 19 UI updates

### Recommended Project Structure
```
backend/app/api/v1/
├── endpoints/
│   ├── jobs.py           # NEW: SSE endpoint (GET /jobs/stream)
│   ├── auth.py           # existing
│   └── ...
├── deps.py               # MODIFY: add get_current_superadmin_sse
├── __init__.py           # MODIFY: register jobs router
└── ...

backend/app/
├── services/
│   ├── sync/
│   │   └── job_tracker.py  # Phase 17 — PUBLISH calls already here (not Phase 18 scope)
│   └── ...
└── ...
```

### Pattern 1: SSE Endpoint with Async Generator

**What:** An async generator function that yields SSE-compatible event dicts (with "event", "data", "id" keys). sse-starlette's EventSourceResponse wraps the generator and handles all HTTP streaming protocol details.

**When to use:** Whenever you need to stream real-time updates to a browser without WebSocket complexity. SSE is built on HTTP/1.1 and works through proxies and firewalls more reliably.

**Example:**
```python
# Source: sse-starlette documentation + Phase 17 context (job_tracker.py, BackgroundJob model)

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select

from app.api.v1.deps import get_current_superadmin_sse
from app.db.base import get_session_factory
from app.models.jobs import BackgroundJob
from app.core.redis import get_redis

router = APIRouter()

async def sse_generator(request: Request, superadmin_user):
    """
    Async generator yielding SSE events for job updates.
    
    D-07: On connect, burst-query 24h of jobs.
    D-02: On each pubsub message (job_id), fetch the BackgroundJob row from DB.
    D-09: Poll request.is_disconnected() after each heartbeat and event send.
    D-08: Yield keepalive ping every 30 seconds.
    """
    redis = get_redis()
    pubsub = None
    
    try:
        # D-07: Initial 24h burst on connect
        async with get_session_factory()() as db:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            result = await db.execute(
                select(BackgroundJob)
                .where(BackgroundJob.started_at > cutoff)
                .order_by(BackgroundJob.started_at.desc())
            )
            jobs = result.scalars().all()
        
        for job in jobs:
            if await request.is_disconnected():
                return
            yield {
                "event": "job_update",
                "data": serialize_job_event(job),  # D-06 minimal payload
                "id": str(job.id)
            }
        
        # D-02 & D-03: Subscribe to live updates
        pubsub = redis.pubsub()
        await pubsub.subscribe("sse:job_updates")
        
        last_ping = datetime.utcnow()
        
        while True:
            # D-09: Check for disconnect after heartbeat
            if await request.is_disconnected():
                break
            
            # D-08: Send ping every 30 seconds
            now = datetime.utcnow()
            if (now - last_ping).total_seconds() >= 30:
                yield {
                    "event": "ping",
                    "data": {"ts": now.isoformat()}
                }
                last_ping = now
            
            # D-02: Get next pubsub message (with timeout to allow ping checks)
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=5  # Check disconnect every 5 seconds
            )
            
            if message:
                job_id_str = message["data"]  # Redis gives us the channel message (job_id)
                
                # D-02: Fetch BackgroundJob from DB by job_id
                async with get_session_factory()() as db:
                    job = await db.get(BackgroundJob, job_id_str)
                    if job:
                        # D-09: Check for disconnect before sending event
                        if await request.is_disconnected():
                            break
                        
                        yield {
                            "event": "job_update",
                            "data": serialize_job_event(job),
                            "id": str(job.id)
                        }
            
            # D-09: Check for disconnect after event send
            if await request.is_disconnected():
                break
            
            # Brief sleep to avoid busy-loop
            await asyncio.sleep(0.1)
    
    finally:
        # D-03: Always unsubscribe and close pubsub connection on disconnect
        if pubsub:
            try:
                await pubsub.unsubscribe("sse:job_updates")
                await pubsub.close()
            except Exception as e:
                logger.warning(f"Error closing pubsub: {e}")


def serialize_job_event(job: BackgroundJob) -> str:
    """
    D-06: Serialize BackgroundJob to minimal event payload.
    
    Returns JSON string with: job_id, job_type, org_id, status, 
    progress_current, progress_total, started_at, ended_at.
    """
    import json
    payload = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "org_id": str(job.org_id),
        "status": job.status,
        "progress_current": job.progress_current,
        "progress_total": job.progress_total,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
    }
    return json.dumps(payload)


@router.get("/stream")
async def stream_jobs(
    request: Request,
    superadmin_user = Depends(get_current_superadmin_sse),
):
    """
    D-04 & D-05: SSE endpoint guarded by SuperAdmin JWT from query param.
    Streams all job updates (global firehose) to connected clients.
    """
    return EventSourceResponse(
        sse_generator(request, superadmin_user),
        ping=15,  # Send infrastructure-level ping every 15s (separate from D-08 ping)
        send_timeout=60,
        headers={"Cache-Control": "no-cache"}
    )
```

### Pattern 2: Query Parameter JWT Validation

**What:** A dependency that extracts JWT from the query parameter instead of the Authorization header. Used because browser EventSource does not support custom headers (D-04).

**When to use:** When a browser-native API (EventSource) cannot send custom headers and the token is available in localStorage (can be passed to EventSource constructor as query param).

**Example:**
```python
# Source: adaptation of backend/app/api/v1/deps.py get_current_superadmin + decode_token from security.py

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.base import get_db
from app.core.security import decode_token
from app.models.user import User

async def get_current_superadmin_sse(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    D-04: Validate SuperAdmin JWT from query parameter 'token'.
    
    Identical logic to get_current_superadmin (check is_superuser flag)
    but reads token from request.query_params["token"] instead of Bearer header.
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

### Pattern 3: Redis Pubsub Connection Lifecycle

**What:** Create a dedicated Redis pubsub connection per SSE client. Do not reuse the singleton `get_redis()` client for SUBSCRIBE operations — create a fresh `redis.from_url()` instance or call `.pubsub()` on a separate client.

**Why:** The Redis protocol requires that a connection be in SUBSCRIBE mode to receive pub/sub messages. A connection in SUBSCRIBE mode cannot execute other commands (like GET, SET). The singleton command client must remain unencumbered.

**Example:**
```python
# Source: redis-py asyncio documentation

redis = get_redis()  # Singleton for PUBLISH operations in job_tracker.py
pubsub = redis.pubsub()  # CORRECT: Creates a dedicated pubsub connection on the same client

# OR (if avoiding shared client state):
pubsub_redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
pubsub = pubsub_redis.pubsub()

# Subscribe and iterate
await pubsub.subscribe("sse:job_updates")

try:
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
        if message:
            yield {"event": "job_update", "data": message["data"]}
finally:
    # Always unsubscribe and close in finally block
    await pubsub.unsubscribe("sse:job_updates")
    await pubsub.close()
```

### Anti-Patterns to Avoid
- **Reusing the singleton command client for SUBSCRIBE:** The client enters SUBSCRIBE mode and cannot execute other commands. Use `.pubsub()` on the client or create a separate instance.
- **Not closing pubsub connections:** Each SSE client holds one Redis connection. Failure to close on disconnect leads to connection pool exhaustion and Uvicorn worker lockup.
- **Polling the DB instead of using pub/sub:** At v1.3 scale (< 50 SuperAdmins), pub/sub is low-overhead. But polling every 1-2 seconds per client × 50 clients = 50 SELECT queries/sec. Pub/sub is only one PUBLISH per job update.
- **Checking is_disconnected() only once per loop:** Browser tab closes, proxies time out, and networks disconnect asynchronously. Check after each major operation (heartbeat, event send, pubsub message).
- **Not using try-finally for cleanup:** Exceptions, network errors, or client crashes can break the loop. try-finally ensures unsubscribe + close always runs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE protocol framing | Custom event encoding (event:, data:, id: prefixes) | sse-starlette EventSourceResponse | SSE has strict line-ending and escaping rules; hand-rolled solutions frequently fail on newlines in data, missing message boundaries, missing ping intervals |
| Async Redis pub/sub connection | Custom subscription loop with try-catch | redis-py pubsub() + async with context manager | Connection lifecycle (subscribe, get_message polling, unsubscribe, close) has edge cases; redis-py handles reconnection, timeout logic, and cleanup |
| JWT token validation from query param | Custom JWT parsing | decode_token() from security.py (Phase 2) | Token validation must check signature, expiry, claim types; rolling custom logic opens timing-attack and expiry-bypass vulnerabilities |
| Client disconnect detection | Catching only CancelledError | await request.is_disconnected() polling + try-finally | CancelledError alone misses graceful browser tab closes; is_disconnected() catches all disconnect modes (tab close, network loss, proxy timeout) |
| 30-second heartbeat timer | Manual datetime comparison | asyncio.sleep(30) + last_ping timestamp | Sleep is reliable across OS and event loop implementations; manual timing can drift or miss ticks under load |

**Key insight:** SSE is a complex protocol (client reconnection, event ID ordering, message boundaries) that sse-starlette handles. Pub/sub connection management has many failure modes (zombie connections, subscription mode conflicts, unhandled exceptions). The ecosystem solutions here are proven at scale and prevent subtle production bugs.

## Common Pitfalls

### Pitfall 1: Forgetting to Unsubscribe on Disconnect
**What goes wrong:** SSE client connects → async generator opens pubsub → client disconnects or network drops → finally block never runs → pubsub connection stays open in Redis → connection pool fills up → new SSE connections fail → Uvicorn worker hangs.

**Why it happens:** Exception handling in async code is subtle. A CancelledError or network error can propagate out of the async generator loop without reaching the finally block if not properly structured. Or developers skip the finally block entirely, assuming the context manager cleanup is enough.

**How to avoid:** 
1. Always wrap the main generator loop in try-finally, even if using async context managers.
2. Explicitly call `await pubsub.unsubscribe()` and `await pubsub.close()` in the finally block.
3. Test disconnect behavior: kill the browser tab mid-stream and verify connection is released (check Redis with `INFO stats` or `CLIENT LIST`).

**Warning signs:** 
- Redis INFO stats shows `connected_clients` growing over time
- Uvicorn logs "worker timeout" or stalled event loop
- New SSE connections fail with "connection pool exhausted"

### Pitfall 2: Checking is_disconnected() Only Once Per Iteration
**What goes wrong:** async generator checks `is_disconnected()` only at the top of the loop → spends 5 seconds waiting for a pubsub message → client disconnects → doesn't check for 5 more seconds → finally block eventually runs, but by then 100+ other SSE clients may have done the same, causing a cascade of delayed cleanups.

**Why it happens:** Developers assume a single check per loop iteration is sufficient. But asyncio.sleep(5) or awaiting a blocking operation is a hidden disconnect race. Proxies can time out; mobile networks drop; tab close is instantaneous.

**How to avoid:**
1. Check `await request.is_disconnected()` after every async operation: after heartbeat yield, after pubsub get_message, after DB query.
2. Use short timeouts on blocking operations (pubsub.get_message(timeout=5), not timeout=60).
3. Yield a heartbeat every 30 seconds (D-08) — this forces a check every 30 seconds at minimum.

**Warning signs:**
- Browser tab closes but SSE connection persists for 30+ seconds before cleanup
- High memory usage on Uvicorn from stalled coroutines

### Pitfall 3: Reusing the Singleton Redis Client for Pub/Sub
**What goes wrong:** SSE generator calls `redis = get_redis()` → enters `async with redis.pubsub()` → subscribes → enters SUBSCRIBE mode → another part of the code (job_tracker.py) tries to call `redis.publish(...)` → blocks because the connection is in SUBSCRIBE mode → deadlock.

**Why it happens:** redis-py's client design allows multiple modes (command, pubsub) but only one can be active per connection at a time. Singleton pattern works for commands, but breaks when mixing SUBSCRIBE and regular operations.

**How to avoid:**
1. Create a separate Redis instance for pubsub: `pubsub_redis = await redis.from_url(...)` or `pubsub = redis.pubsub()` on the singleton.
2. Never call regular Redis commands (GET, SET, PUBLISH) on a connection that's in SUBSCRIBE mode.
3. Document in code comments: "This connection is SUBSCRIBE-only; never call regular Redis commands on it."

**Warning signs:**
- AsyncIO deadlock warnings: "Timeout waiting for pubsub message"
- Job updates are published but SSE clients don't receive them

### Pitfall 4: EventSourceResponse Ping Conflicts with D-08 Custom Ping
**What goes wrong:** EventSourceResponse has a built-in `ping` parameter (default 15 seconds) that sends infrastructure-level pings. But D-08 requires a 30-second custom `ping` event with a timestamp. If both are enabled, clients receive two different keepalive messages with different intervals, confusing the frontend or proxy.

**Why it happens:** sse-starlette's ping is a Starlette-level keep-alive for the HTTP connection. D-08's ping is a custom SSE event for the browser application. They serve different purposes but look similar to naive implementations.

**How to avoid:**
1. Set `ping=15` on EventSourceResponse for HTTP keep-alive (prevents proxy timeouts).
2. Separately yield `{"event": "ping", "data": {"ts": ...}}` every 30 seconds from the generator for application-level heartbeat.
3. Document in code: "ping parameter is for HTTP-level keep-alive; custom ping event is for app-level monitoring."

**Warning signs:**
- Frontend receives both `ping` (no event type) and `job_update` events; code is confused
- Proxy logs show connection resets every 30 seconds (mismatch between HTTP ping and app ping)

### Pitfall 5: Querying DB Without a Fresh Session in the Loop
**What goes wrong:** SSE generator holds one AsyncSession for the entire lifetime of the connection → every iteration tries to re-execute a query on the same session → SQLAlchemy complains about expired objects or connection pool leaks → session is never returned to the pool.

**Why it happens:** D-14 from Phase 17 established a "session-per-operation" pattern for job_tracker.py. But SSE generators can live for minutes or hours, so one session for the whole lifetime violates that pattern and leaks resources.

**How to avoid:**
1. Follow D-14: Open a fresh session, query, close, repeat for each job fetch.
2. Use `async with get_session_factory()() as db:` for every DB operation.
3. Never keep a session alive across multiple async operations.

**Warning signs:**
- "SQLAlchemy pool size exceeded" errors after 30+ minutes of SSE streaming
- Uvicorn worker memory grows over time while SSE client is connected

## Code Examples

Verified patterns from official sources and codebase:

### Pattern: Minimal Event Payload (D-06)

```python
# Source: CONTEXT.md D-06 + job_tracker.py + jobs.py model

def serialize_job_event(job: BackgroundJob) -> str:
    """Serialize BackgroundJob to D-06 minimal payload.
    
    Includes: job_id, job_type, org_id, status, progress_current,
    progress_total, started_at, ended_at.
    
    Does NOT include: output, error, metadata (fetch via separate REST call in Phase 19).
    """
    import json
    payload = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "org_id": str(job.org_id),
        "status": job.status,
        "progress_current": job.progress_current,
        "progress_total": job.progress_total,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
    }
    return json.dumps(payload)
```

### Pattern: Disconnect Detection Loop

```python
# Source: sse-starlette docs + FastAPI asyncio examples

import asyncio
from datetime import datetime

async def sse_generator(request: Request):
    """Template for safe disconnect detection in async generator."""
    try:
        while True:
            # Check before any blocking operation
            if await request.is_disconnected():
                break
            
            # Heartbeat every 30 seconds
            yield {"event": "ping", "data": {"ts": datetime.utcnow().isoformat()}}
            
            # Wait with timeout; re-check disconnect frequently
            for _ in range(6):  # 6 * 5 second waits = 30 second total
                if await request.is_disconnected():
                    return
                await asyncio.sleep(5)
            
            # Or use a single sleep with frequent checks:
            # last_check = asyncio.get_event_loop().time()
            # while True:
            #     if await request.is_disconnected():
            #         return
            #     await asyncio.sleep(0.5)
            #     if asyncio.get_event_loop().time() - last_check > 30:
            #         break
    finally:
        # Cleanup always runs, even on exception
        # Close pubsub, cancel pending tasks, etc.
        pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket for real-time updates | Server-Sent Events (SSE) | 2023+ (standard now) | SSE is simpler (HTTP-based, unidirectional), works through proxies better, doesn't require complex handshake |
| Polling DB directly | Redis pub/sub notification bus | Phase 18 decision (D-01) | Pub/sub is lower latency, uses less CPU, scales better; polling at v1.3 scale would be 50+ SELECT/sec |
| Flask/Tornado + manual streaming | FastAPI + sse-starlette | 2023+ | sse-starlette handles protocol edge cases (client reconnect, frame boundaries, ping intervals); modern async/await syntax cleaner than callbacks |
| Custom JWT validation in endpoint | Dependency injection (Depends) | Phase 2 pattern | Reusable, testable, DRY; reduces auth bugs |

**Deprecated/outdated:**
- **Manual SSE frame encoding** (e.g., `f"event: job_update\ndata: {json.dumps(...)}\n\n"`): sse-starlette handles this correctly; hand-rolled encoding has edge cases around newlines and binary data.
- **Long-lived DB sessions** in streaming: Session-per-operation pattern (D-14) must be followed; one session for 10+ minutes leaks connection pool slots.
- **Polling with sleep(1) intervals**: asyncio.sleep(1) × 50 clients = 50 wakeups/sec, CPU waste. Use event-driven pub/sub instead.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis server | pub/sub notification bus | ✓ | Configured via settings.REDIS_URL | None — if Redis unavailable, SSE cannot subscribe to job updates |
| PostgreSQL | BackgroundJob fetch on each pubsub message | ✓ | 15.4+ (verified in Phase 16/17) | None — DB is already required |
| Python asyncio | Event loop for async generator + sleep | ✓ | Built-in (3.10+) | None — required for all FastAPI apps |

**Missing dependencies with no fallback:**
- Redis server — if down, job updates will not stream to SuperAdmins. Phase 19 UI will appear frozen without updates.

**Missing dependencies with fallback:**
- (None identified) — all required services are already available.

**Step 2.6 Result:** All external dependencies verified available. No fallback strategies needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already in requirements.txt) |
| Config file | None — pytest uses discovery (tests/ directory, test_*.py files) |
| Quick run command | `pytest backend/tests/test_sse.py -v -x` (new file, Wave 0) |
| Full suite command | `pytest backend/tests/ -v --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SSE-01 | EventSourceResponse yields job_update events; mock pubsub publishes job_id, SSE fetches from DB, event is yielded | unit | `pytest backend/tests/test_sse.py::test_sse_yields_job_update -x` | ❌ Wave 0 |
| SSE-01 | EventSourceResponse rejects non-SuperAdmin JWT; token validation fails → 403 | unit | `pytest backend/tests/test_sse.py::test_sse_rejects_non_superadmin -x` | ❌ Wave 0 |
| SSE-01 | Initial 24h burst: on client connect, SSE queries BackgroundJob WHERE started_at > (now - 24h) and yields each as job_update | unit | `pytest backend/tests/test_sse.py::test_sse_burst_24h_on_connect -x` | ❌ Wave 0 |
| SSE-02 | SSE yields ping event every 30 seconds; client waits 35s without pubsub message, receives ping | unit | `pytest backend/tests/test_sse.py::test_sse_heartbeat_30s -x` | ❌ Wave 0 |
| SSE-02 | On client disconnect (request.is_disconnected() = True), async generator breaks loop; finally block runs; pubsub.unsubscribe + pubsub.close called | unit | `pytest backend/tests/test_sse.py::test_sse_cleanup_on_disconnect -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_sse.py -v -x` (< 30 seconds)
- **Per wave merge:** `pytest backend/tests/ -v --tb=short` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_sse.py` — SSE endpoint unit tests (generator, token validation, 24h burst, heartbeat, cleanup)
- [ ] `backend/tests/conftest.py` — existing; may need mock_pubsub fixture
- [ ] Fixtures for mocking: `mock_redis_pubsub`, `mock_request`, `async_generator_to_list()` helper

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*

Actually, Wave 0 gaps identified — conftest.py already exists but needs SSE-specific mocks.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | JWT token validation via decode_token (Phase 2 pattern); query param extraction (D-04) |
| V3 Session Management | yes | SSE connection = session; closed on disconnect (D-09); 30-minute token TTL forces reconnect cycle |
| V4 Access Control | yes | SuperAdmin check via is_superuser flag in get_current_superadmin_sse dependency |
| V5 Input Validation | yes | Query parameter token is validated via decode_token before any SSE generator execution; no user input in event payloads |
| V6 Cryptography | yes | JWT signature verified via decode_token (Phase 2); uses settings.ALGORITHM (HS256) and settings.SECRET_KEY |
| V7 Encryption | yes | Redis connection uses settings.REDIS_URL (redis:// or redis+ssl://); configure TLS if needed per deployment |
| V8 Error Handling | yes | Exceptions in async generator caught in try-finally; no stack traces exposed in SSE events; errors logged server-side |

### Known Threat Patterns for {FastAPI + Redis Pub/Sub + SSE}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized SSE access (non-SuperAdmin) | Spoofing | get_current_superadmin_sse validates JWT before stream creation; verify is_superuser flag (not just auth) |
| Token exposure in query parameter (HTTP logs) | Information Disclosure | Token TTL = 30 min; force HTTPS in production (Uvicorn should run behind reverse proxy with SSL termination); consider rate-limiting token generation per IP |
| Redis pubsub injection (malicious job_id published) | Tampering | job_id comes from PUBLISH in job_tracker.py (trusted source, Phase 17); validate job_id is UUID before DB query |
| DoS: Millions of pub/sub messages flood SSE | Denial of Service | SSE client processes one message per iteration; if pubsub is flooded, worst case is backend CPU usage (cannot DoS client). Monitor Redis PUBLISH rate. |
| Resource exhaustion: 1000 SSE clients = 1000 pubsub connections | Denial of Service | Uvicorn worker pool is finite (default ~10 workers). At 50+ concurrent SuperAdmins, each holding one connection, watch for pool saturation. SSE-03 (future) will add Redis pub/sub backend to share subscriptions. For now, configure Uvicorn `--workers N` based on expected concurrent SuperAdmins. |
| Replay attack: Attacker replays old captured JWT | Repudiation | JWT includes `exp` claim (30-min TTL from decode_token logic). Captured tokens expire; attacker cannot use them after 30 min. No replay of events — each client maintains its own pubsub subscription. |

**Phase 18 security posture:** Internal SuperAdmin tool with JWT auth. Threat model is protecting from unauthorized org users accessing SSE, not from external attackers. Standard ASVS controls sufficient; no special hardening required beyond Phase 2 auth patterns.

## Sources

### Primary (HIGH confidence)
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) - Verified latest version 3.4.2 (released May 6, 2026); W3C SSE spec compliance; native async/await
- [sse-starlette Context7](https://context7.com/sysid/sse-starlette/llms.txt) - EventSourceResponse async generator API, ping interval, send_timeout parameters
- [redis-py asyncio examples](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) - Verified pubsub lifecycle pattern: `.pubsub()` instance, `subscribe()`, `get_message()`, `unsubscribe()`, `close()` in finally block
- Codebase review: [backend/app/api/v1/deps.py](../../../backend/app/api/v1/deps.py) - get_current_superadmin pattern (lines 67–81), token validation, is_superuser check
- Codebase review: [backend/app/core/security.py](../../../backend/app/core/security.py) - decode_token function (lines 52–57) — used by get_current_superadmin_sse
- Codebase review: [backend/app/services/sync/job_tracker.py](../../../backend/app/services/sync/job_tracker.py) - Session-per-operation pattern (D-14); update_background_job signature; where PUBLISH calls must be added (Phase 17 concern, not Phase 18)

### Secondary (MEDIUM confidence)
- [FastAPI Request.is_disconnected() discussion](https://github.com/fastapi/fastapi/discussions/7572) - Confirmed is_disconnected() polling pattern; usage in async generators; verification with try-finally cleanup
- [GitHub: Starlette streaming with client disconnect](https://github.com/Kludex/starlette/discussions/2866) - Request.is_disconnected() reliability; asyncio.CancelledError handling
- [WebSearch: FastAPI 0.115.0 streaming](https://dasroot.net/posts/2026/03/async-streaming-responses-fastapi-comprehensive-guide/) - Confirms 0.115.0 supports async generators; EventSourceResponse + sse-starlette compatibility

### Tertiary (LOW confidence — marked for validation)
- General async/await patterns — training data, not verified against 2026 codebase (LOW, standard language feature)
- Connection pool exhaustion mechanics — common knowledge, not verified against specific Uvicorn version (LOW, recommend manual testing in Phase 18)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Job updates published by job_tracker.py via PUBLISH (Phase 17) will be available to SSE generator's pubsub subscription | Integration Pattern / D-01 | If Phase 17 does not add PUBLISH calls, SSE will never receive notifications. Verify job_tracker.py has PUBLISH calls before Phase 18 testing. |
| A2 | get_current_superadmin dependency requires only is_superuser flag check; no additional org-level authorization needed for global firehose | Authorization (D-05) | If SuperAdmins should only see jobs from their org, D-05 is wrong. Verify this is truly a "global firehose" with user. |
| A3 | Uvicorn pool size adequate for expected concurrent SuperAdmin count; no need for SSE-specific worker tuning in Phase 18 | Environment scaling | If 50+ SuperAdmins connect simultaneously, Uvicorn may hit worker pool limits. Recommendation: measure at Phase 19 UAT and adjust for Phase 20 if needed. |
| A4 | request.is_disconnected() polling with asyncio.sleep(0.1) in a tight loop will detect client disconnect within 5 seconds | Disconnect latency (D-09) | If actual latency is > 5s (e.g., proxy caches disconnect for 30s), connection cleanup delays. Phase 19 UAT will expose real latency. |

**All other claims were verified:** sse-starlette 3.4.2 exists and is current, redis-py pubsub API confirmed, JWT validation pattern confirmed in codebase, FastAPI 0.115.0 supports async generators, DeclarativeBase pattern (SQLAlchemy 2.0) confirmed in codebase.

## Open Questions

1. **When are PUBLISH calls added to job_tracker.py?**
   - What we know: Phase 17 instrumentation was marked "complete 2026-05-11" (STATE.md), but D-01 requires PUBLISH calls in create_background_job and update_background_job
   - What's unclear: Did Phase 17 actually implement PUBLISH, or is that a Phase 18 responsibility?
   - Recommendation: Verify Phase 17's 17-01-PLAN.md or 17-02-PLAN.md covers PUBLISH implementation before Phase 18 starts. If not, a short Phase 18 task to add PUBLISH to job_tracker.py must happen first.

2. **How many concurrent SuperAdmin connections should we expect at v1.3 launch?**
   - What we know: STATE.md says "At Phase 18 start: confirm actual SuperAdmin headcount for --limit-concurrency and --workers tuning"
   - What's unclear: Is this 5? 20? 50+? Impacts Uvicorn configuration and whether SSE-03 (Redis pub/sub backend) is urgent.
   - Recommendation: Planning should include a question to the user about expected concurrent SuperAdmin count.

3. **Should EventSourceResponse ping parameter match D-08's 30-second heartbeat, or be separate?**
   - What we know: EventSourceResponse has a built-in `ping` parameter (default 15s); D-08 requires a custom `ping` event every 30s
   - What's unclear: Are these two independent mechanisms (HTTP keep-alive vs. app keep-alive), or should they be synchronized?
   - Recommendation: Research suggests both are needed (HTTP-level ping for proxy, app-level ping for frontend). Plan should include both.

## Metadata

**Confidence breakdown:**
- Standard stack (sse-starlette, redis-py): **HIGH** — Verified via PyPI, official docs, Context7; versions confirmed current
- Architecture (async generator, pubsub lifecycle): **HIGH** — Verified via redis-py examples, sse-starlette docs, codebase patterns
- Auth pattern (query param JWT): **HIGH** — Verified via codebase; decode_token confirmed in security.py
- Pitfalls (connection cleanup, disconnect detection): **MEDIUM** — Based on known async/await gotchas and GitHub discussions; not 100% verified against this specific codebase under load
- Environment availability: **HIGH** — Redis, PostgreSQL, Python verified in requirements.txt and config
- Validation architecture: **MEDIUM** — Test patterns inferred from Phase 17 structure; specific fixtures not yet written

**Research date:** 2026-05-11
**Valid until:** 2026-05-25 (14 days — sse-starlette is stable; FastAPI 0.115.0 is stable; redis-py 5.0 is stable)

---

*Phase: 18-sse-transport*
*Research gathered: 2026-05-11 by gsd-phase-researcher (Haiku 4.5)*
