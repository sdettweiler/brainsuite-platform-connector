# Phase 18: SSE Transport - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose a FastAPI Server-Sent Events endpoint that streams real-time job updates to connected SuperAdmin browsers. When any background job is created or updated, the endpoint pushes a minimal `job_update` event (or a `ping` keepalive) to all connected SuperAdmin clients. Connection leaks are prevented via `request.is_disconnected()` checks; proxy timeouts are prevented via 30-second heartbeats.

This phase does NOT build any Angular UI (Phase 19), does NOT build a REST jobs query endpoint (also Phase 19 concern), and does NOT implement Redis pub/sub at scale (SSE-03 is a future requirement). It is purely the backend streaming transport layer.

</domain>

<decisions>
## Implementation Decisions

### Notification Bus (how SSE learns of job changes)

- **D-01:** Use Redis PUBLISH/SUBSCRIBE as the notification mechanism. `job_tracker.py` calls `PUBLISH sse:job_updates <job_id_uuid>` after every `BackgroundJob` create or update. This is the same Redis client singleton already in `backend/app/core/redis.py`.
- **D-02:** The SSE generator opens a dedicated Redis SUBSCRIBE connection on `sse:job_updates`. On each message, it fetches the specific `BackgroundJob` row from PostgreSQL by `job_id`, then pushes the event. Redis carries the signal; PostgreSQL is the source of truth.
- **D-03:** Each SSE client holds one dedicated Redis pubsub connection for the duration of the stream. On disconnect (detected via `request.is_disconnected()`), the generator exits and must cleanly unsubscribe and close the pubsub connection.

### Token Delivery (authentication for EventSource)

- **D-04 (Claude's discretion):** The SSE endpoint accepts the SuperAdmin JWT via query parameter: `GET /api/v1/jobs/stream?token=<access_jwt>`. Browser `EventSource` does not support custom headers, and the access token is in localStorage (not a cookie). A dedicated `get_current_superadmin_sse` dependency reads from `request.query_params["token"]` and validates it identically to `get_current_superadmin`. Acceptable security tradeoff for an internal SuperAdmin-only endpoint with a 30-minute token TTL.

### Event Payload & Scope

- **D-05:** Global firehose — all connected SuperAdmins receive updates for all jobs across all orgs and all job types. No server-side filtering. Phase 19 filters by type/status client-side.
- **D-06:** Minimal snapshot event payload. Each `job_update` event includes:
  ```json
  {
    "job_id": "<uuid>",
    "job_type": "<sync_daily|sync_full|sync_initial|sync_historical|download|autofill|scoring>",
    "org_id": "<uuid>",
    "status": "<PENDING|RUNNING|COMPLETE|FAILED>",
    "progress_current": 0,
    "progress_total": null,
    "started_at": "<iso8601>",
    "ended_at": null
  }
  ```
  `output` and `error` JSONB are NOT included in SSE events — Phase 19 drill-in panels fetch those via a separate REST `GET /jobs/{id}` endpoint (to be built in Phase 19).
- **D-07:** On new client connection, immediately query `background_jobs WHERE started_at > (now() - 24h)` and push each row as a `job_update` event before entering the live subscription loop. This bootstraps Phase 19's UI without a separate REST call.

### Keepalive & Disconnect

- **D-08:** Heartbeat interval: **30 seconds**. Keepalive event format:
  ```
  event: ping
  data: {"ts": "<iso8601>"}
  ```
- **D-09:** Client disconnect detection: `await request.is_disconnected()` checked in the async generator loop after each heartbeat tick and after each event send. On `True`, break the loop and proceed to Redis pubsub cleanup.
- **D-10:** No maximum connection TTL — the connection lives until the client disconnects. The 30-minute access token naturally forces a reconnect cycle, which is sufficient.

### Claude's Discretion

- Token delivery (D-04): query parameter chosen as the pragmatic solution for an internal SuperAdmin tool; the user delegated this decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — SSE-01 and SSE-02 (full requirement text + acceptance criteria)
- `.planning/ROADMAP.md` §Phase 18 — Success criteria for this phase (4 criteria)

### Schema
- `backend/app/models/jobs.py` — `BackgroundJob` model: all columns, types, indexes. SSE events are a subset of this schema (D-06).

### Existing Services (Integration Points)
- `backend/app/services/sync/job_tracker.py` — `create_background_job` and `update_background_job` helpers. D-01 requires adding `PUBLISH sse:job_updates <job_id>` calls here after each DB write.
- `backend/app/core/redis.py` — `get_redis()` singleton. SSE generator and job_tracker both use this. Note: pubsub requires a separate connection from the command connection — do NOT reuse the singleton for SUBSCRIBE; create a new `aioredis.Redis` instance or use `.pubsub()` on the existing client.
- `backend/app/api/v1/deps.py` — `get_current_superadmin` (L64–L73): template for the new `get_current_superadmin_sse` dep that reads from query param instead of Bearer header.
- `backend/app/api/v1/__init__.py` — router registration. New SSE router must be added here.

### Auth Pattern
- `backend/app/api/v1/endpoints/auth.py` §login — shows `decode_token` usage and token validation flow; `get_current_superadmin_sse` must replicate token validation logic from `get_current_user` adapted for query param input.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_redis()` in `backend/app/core/redis.py` — singleton async Redis client. Use `.pubsub()` on a fresh `aioredis.from_url(...)` instance for SUBSCRIBE (do not share the pubsub connection with command operations).
- `get_current_superadmin` in `backend/app/api/v1/deps.py` (L64–L73) — copy and adapt for query-param token input.
- `BackgroundJob` model at `backend/app/models/jobs.py` — serialize a row to the D-06 event payload.
- `get_session_factory()` in `backend/app/db/base.py` — for the initial burst query (D-07) and per-event DB fetch (D-02); follow session-per-operation pattern from Phase 17 D-14.

### Established Patterns
- **Session-per-operation**: `async with get_session_factory()() as db:` — required for every DB read inside the SSE loop.
- **FastAPI `StreamingResponse` / `sse-starlette`**: `sse-starlette==3.4.2` is the planned new package (from v1.3 milestone decisions). Use `EventSourceResponse` from `sse_starlette.sse` which handles SSE framing, `Content-Type: text/event-stream`, and keep-alive headers automatically.
- **Router registration pattern**: all routers in `backend/app/api/v1/__init__.py` follow `api_router.include_router(X.router, prefix="/X", tags=["X"])`.

### Integration Points
- `backend/app/services/sync/job_tracker.py` — every call to `update_background_job(...)` must also PUBLISH the job_id to Redis (D-01). This is the only change needed in Phase 17 code to wire up the SSE feed.
- New file: `backend/app/api/v1/endpoints/jobs.py` — SSE endpoint router (`GET /jobs/stream`).
- New file: `backend/app/api/v1/endpoints/jobs.py` — also a candidate for a future `GET /jobs/{id}` REST endpoint (Phase 19 concern — do not build in Phase 18).

</code_context>

<specifics>
## Specific Ideas

- The `sse_starlette` `EventSourceResponse` wraps an async generator — the generator yields dicts with `event`, `data`, and optional `id` keys. The keepalive ping (`event: ping`) and job update (`event: job_update`) are both yielded from the same generator.
- Redis pubsub connection lifecycle: `pubsub = redis_client.pubsub()` → `await pubsub.subscribe("sse:job_updates")` on connection open → `await pubsub.unsubscribe()` + `await pubsub.close()` on disconnect (in a `finally` block or after the `is_disconnected` break).
- Phase 19 will need a `GET /api/v1/jobs` (list, last 24h) and `GET /api/v1/jobs/{id}` (detail with output/error) REST endpoints — not in Phase 18 scope, but the planner should note them as adjacent work.

</specifics>

<deferred>
## Deferred Ideas

- **Redis pub/sub scaling (SSE-03)**: Full pub/sub backend upgrade for 50+ concurrent SuperAdmin connections is explicitly a future requirement. Phase 18's pub/sub foundation is already compatible — SSE-03 would add sharding or cluster-aware subscription.
- **Last-Event-ID reconnect support**: Browser EventSource auto-reconnects and sends `Last-Event-ID` header. Phase 18 does not need to implement replay — the initial 24h burst on reconnect is sufficient for the SuperAdmin use case.
- **`GET /jobs` and `GET /jobs/{id}` REST endpoints**: Needed by Phase 19 drill-in panels but explicitly out of Phase 18 scope.

</deferred>

---

*Phase: 18-sse-transport*
*Context gathered: 2026-05-11*
