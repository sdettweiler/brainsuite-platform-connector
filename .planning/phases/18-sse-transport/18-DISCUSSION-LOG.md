# Phase 18: SSE Transport - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 18-sse-transport
**Areas discussed:** Notification bus, Token delivery, Event payload & scope, Keepalive & disconnect

---

## Notification Bus

| Option | Description | Selected |
|--------|-------------|----------|
| DB polling | SSE generator queries background_jobs on a timer — no new infra, latency = poll interval | |
| Redis key-based signal | job_tracker writes Redis keys after each DB update; SSE polls Redis for new keys | |
| Redis SUBSCRIBE | job_tracker PUBLISH to channel; SSE generator SUBSCRIBE per connection | ✓ |
| In-process asyncio.Event | Global event set by job_tracker; only works single-worker | |

**User's choice:** Redis SUBSCRIBE on a dedicated channel (`sse:job_updates`)

**Follow-up Q — what does the generator do on receipt?**

| Option | Selected |
|--------|----------|
| Fetch specific updated job from DB (signal = job_id) | ✓ |
| Re-fetch all recent jobs from DB | |
| Embed full payload in Redis (no DB round-trip) | |

**Follow-up Q — how does the generator listen?**

| Option | Selected |
|--------|----------|
| Poll Redis KEYS sse:job_updated:* on short interval | |
| Redis SUBSCRIBE on dedicated channel | ✓ |
| You decide | |

**Notes:** User committed to full Redis pub/sub from the start. job_tracker.py publishes the job_id UUID string as the message payload. PostgreSQL remains source of truth for job data.

---

## Token Delivery

| Option | Description | Selected |
|--------|-------------|----------|
| JWT via query parameter | GET /stream?token=<jwt> | (delegated) |
| httpOnly auth cookie | Read existing httpOnly cookie — but access token is NOT in a cookie | |
| @microsoft/fetch-event-source | Custom headers via npm dep on frontend | |

**User's choice:** "You decide" — delegated to Claude

**Claude's discretion:** Query parameter (`?token=<jwt>`) chosen as the pragmatic solution. The access token is in localStorage (not a cookie), EventSource doesn't support headers. Internal SuperAdmin tool with 30-min token TTL makes query param an acceptable tradeoff.

---

## Event Payload & Scope

**Scope question:**

| Option | Selected |
|--------|----------|
| Global firehose — all jobs, all orgs | ✓ |
| Filtered by org | |
| Filtered by job_type | |

**Payload question:**

| Option | Selected |
|--------|----------|
| Minimal snapshot (no output/error JSONB) | ✓ |
| Full BackgroundJob row including output/error | |

**Initial burst question:**

| Option | Selected |
|--------|----------|
| Yes — send last 24h of jobs on connect | ✓ |
| No — pure real-time only | |
| You decide | |

**Notes:** Phase 19 drill-in panels will fetch output/error via a separate REST endpoint. SSE events stay small and fast.

---

## Keepalive & Disconnect

**Heartbeat interval:**

| Option | Selected |
|--------|----------|
| 30 seconds | ✓ |
| 15 seconds | |
| You decide | |

**Disconnect detection:**

| Option | Selected |
|--------|----------|
| await request.is_disconnected() in loop | ✓ |
| Catch asyncio.CancelledError | |
| Both (belt-and-suspenders) | |

**Connection TTL:**

| Option | Selected |
|--------|----------|
| No TTL — connection lives until client disconnects | ✓ |
| Hard TTL (e.g. 1 hour) | |

**Notes:** 30-minute access token provides a natural reconnect cycle. `is_disconnected()` is sufficient for clean disconnect handling.

---

## Claude's Discretion

- **Token delivery**: Query parameter (`?token=<jwt>`) — user delegated this decision. Rationale: access token is in localStorage, not a cookie; EventSource doesn't support headers; internal SuperAdmin tool.

## Deferred Ideas

- **SSE-03 (Redis pub/sub scaling)**: 50+ concurrent SuperAdmin connections — explicitly a future requirement
- **Last-Event-ID reconnect replay**: Not needed for Phase 18; initial 24h burst on reconnect is sufficient
- **`GET /jobs` and `GET /jobs/{id}` REST endpoints**: Phase 19 scope
