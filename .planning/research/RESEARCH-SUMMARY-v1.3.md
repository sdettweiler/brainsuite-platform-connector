# Research Summary: v1.3 SSE Real-Time Monitoring + TikTok Asset Download

**Domain:** Multi-tenant SaaS platform real-time job monitoring + asset download completion  
**Researched:** 2026-05-07  
**Overall confidence:** HIGH

## Executive Summary

The v1.3 milestone requires three core additions: (1) real-time job status streaming to SuperAdmin UI via Server-Sent Events, (2) PostgreSQL job persistence with heterogeneous job metadata storage via JSONB, and (3) TikTok video asset download completion (currently returns TikTok cover image URL only, not actual video content). All three additions require MINIMAL changes to existing stack:

- **SSE:** Add `sse-starlette==3.4.2` (single package, 28 KB), use browser-native EventSource API on frontend (no npm install).
- **Job persistence:** Use SQLAlchemy 2.0's native JSONB support (already in stack) + create `background_jobs` table via Alembic.
- **TikTok download:** yt-dlp already in `requirements.txt` (used for YouTube cookies). Extend existing download logic from cover image to full video.

**No new infrastructure required.** Continue using FastAPI `BackgroundTasks` + APScheduler. No distributed queue system (Celery, RabbitMQ) justified at current scale.

## Key Findings

**Stack:** Single new backend package (sse-starlette 3.4.2). EventSource is browser-native. JSONB and asyncpg already in place.

**Architecture:** SSE endpoint pushes job updates via `EventSourceResponse`. Frontend wraps EventSource in RxJS Observable. JSONB allows single `background_jobs` table for all job types.

**Critical pitfall:** Don't add Celery, WebSocket, or separate queue system—overhead not justified. Keep fire-and-forget BackgroundTasks pattern.

## Implications for Roadmap

### Recommended Phase Structure for v1.3

**Phase 1: PostgreSQL Job Persistence Layer**
- Create `background_jobs` table with Alembic migration (JSONB output column)
- Create SQLAlchemy `BackgroundJob` ORM model
- Instrumentation hooks: Update status/progress in existing sync, download, autofill, scoring jobs
- Rationale: Foundation for all real-time features. Can test without SSE endpoint.
- Avoids: Schema churn by using JSONB instead of rigid columns per job type

**Phase 2: SSE Real-Time Transport (Backend)**
- Add `sse-starlette==3.4.2` to requirements.txt
- Create FastAPI SSE endpoint: `@app.get("/api/v1/jobs/{job_id}/stream")` returning `EventSourceResponse`
- Endpoint reads from `background_jobs` table, yields updates as JSON events
- Rationale: Write endpoint independently of frontend to test with curl/curl -N
- Avoids: Change detection gotchas by completing backend contract first

**Phase 3: EventSource Client (Frontend)**
- Wrap browser EventSource in RxJS Observable service (`JobMonitorService`)
- Subscribe in SuperAdmin monitoring UI component
- Parse JSON events, update NgRx store with job status/progress
- Rationale: Trivial implementation (no npm install), leverages existing RxJS
- Avoids: Complex WebSocket lifecycle management

**Phase 4: TikTok Video Asset Download**
- Extend existing `_download_tiktok_thumbnail()` method to download full video via yt-dlp
- Store video to MinIO/GCS using existing boto3 pattern
- Wire into sync job, emit progress events to SSE stream
- Rationale: Unblocks AI autofill + BrainSuite scoring for TikTok creatives
- Avoids: Re-architecture of existing download pattern

**Phase 5: SuperAdmin Job Monitoring UI**
- Build `/configuration/admin` tab: "Active Jobs" section
- List running jobs grouped by type (sync, download, autofill, scoring)
- Per-job progress bar, expand-to-detail panel showing JSONB output (errors, asset counts, etc.)
- Drill-in: Full Gemini output, asset download manifest, error traceback
- Rationale: UI should be last phase so data is complete and testable before UI builds

Phase ordering rationale:
- Persistence → Transport → Client → Data Source → UI ensures each layer can be tested independently
- Backend-first approach catches infrastructure issues before UI work
- TikTok download wired into sync job, so SSE can track progress in real-time

Research flags for phases:
- **Phase 1 (Persistence):** Standard Alembic + SQLAlchemy, LOW research risk
- **Phase 2 (SSE Backend):** sse-starlette well-documented, event streaming pattern standard, LOW risk
- **Phase 3 (EventSource Client):** Browser native API, RxJS wrapper trivial, LOW risk
- **Phase 4 (TikTok Download):** yt-dlp well-established for TikTok (used by researchers), but actual TikTok API metadata extraction (which TikTok endpoints to call) may need validation during phase — MEDIUM risk
- **Phase 5 (UI):** Angular Material components + ECharts (both in stack), LOW risk

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | sse-starlette v3.4.2 verified live on PyPI, EventSource is W3C standard, JSONB native to SQLAlchemy 2.0 / PostgreSQL |
| Features | HIGH | All three features are well-scoped: SSE endpoint, job table, TikTok download. No ambiguity in requirements. |
| Architecture | HIGH | Layered design (Persistence → Transport → Client → Data → UI) is standard for streaming systems. No unusual patterns. |
| Pitfalls | MEDIUM | Main risk is scope creep (adding Celery, WebSocket, job persistence for APScheduler). Mitigated by explicit decision to NOT add. TikTok download extensibility (which API endpoints) may surface during Phase 4. |

## Gaps to Address

1. **TikTok API metadata completeness:** v1.3 should determine whether `_fetch_cover_image_url()` call in `tiktok_sync.py` handles all ad creative scenarios (video, carousel, collection). If missing scenarios exist, Phase 4 may require extending TikTok API integration.

2. **APScheduler job persistence future:** Current implementation uses in-memory dict. If platform grows to multi-worker deployment, may want to migrate APScheduler `jobstore` to PostgreSQL. Out of scope for v1.3, but flag for v1.4 planning.

3. **SSE client reconnection behavior:** Browser EventSource automatically reconnects, but what is expected UX if SuperAdmin closes/reopens monitoring panel? Does UI resume from last job state or fetch full job list? Phase 3 should clarify.

4. **JSONB query patterns:** Once Phase 1 is live, can query job output (e.g., `SELECT * FROM background_jobs WHERE output->'error' IS NOT NULL`). Phase 5 UI should leverage this for filtering/drill-in. Document query patterns early.

---

## Detailed Findings by Domain

### Stack (See STACK-v1.3.md)

**Single new package:** `sse-starlette==3.4.2` (production-ready W3C SSE spec)
- Handles connection lifecycle, graceful shutdown, event ID tracking
- Smaller footprint than WebSocket (no bi-directional overhead)
- Compatible with FastAPI 0.115.0 via transitive Starlette dependency

**Frontend:** Browser-native EventSource (W3C standard, no npm install)
- RxJS wrapper converts EventSource stream to Observable
- Works with Angular 17 change detection via NgZone or Signals

**Database:** SQLAlchemy 2.0 JSONB (native support for PostgreSQL)
- Avoids schema explosion for heterogeneous job types
- Queryable via PostgreSQL JSON operators

**TikTok download:** yt-dlp already in requirements.txt
- Used for YouTube DV360 cookie downloads
- Supports TikTok video + metadata extraction
- Standard ecosystem practice (no alternatives viable)

**What NOT to add:**
- Celery/RabbitMQ: Overhead not justified (BackgroundTasks + APScheduler sufficient)
- WebSocket: Unidirectional push + polling fallback sufficient for monitoring
- New job queue libraries: No persistence needed beyond database

### Architecture (Key Patterns)

**SSE Streaming Pattern:**
```python
@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_updates(job_id: str, request: Request):
    async def generate():
        while True:
            job = await db.get_background_job(job_id)
            yield {"data": json.dumps({"status": job.status, "progress": job.progress_pct})}
            if job.status in ("COMPLETE", "FAILED"):
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(generate())
```

**Frontend Observable Wrapper:**
```typescript
subscribeToJobUpdates(jobId: string): Observable<any> {
  return new Observable(observer => {
    const es = new EventSource(`/api/v1/jobs/${jobId}/stream`);
    es.onmessage = (e) => observer.next(JSON.parse(e.data));
    es.onerror = () => observer.error('Failed');
    return () => es.close();
  });
}
```

**Heterogeneous Job Storage (JSONB):**
- Single `background_jobs` table for sync, download, autofill, scoring jobs
- `job_type` column routes to handler
- `output` JSONB column holds type-specific data (asset counts, error traces, gemini output, etc.)
- Queryable: `SELECT * FROM background_jobs WHERE output->'error' IS NOT NULL`

### Pitfalls (What Can Go Wrong)

**Critical:**
1. **Adding Celery/WebSocket "just in case":** Adds months of complexity (broker management, pub/sub coordination, client lifecycle). Current BackgroundTasks + APScheduler proven sufficient. Decision: NO. Blocks on this.

2. **Polling as fallback in SSE handler:** If SSE endpoint logic tries to poll job status while yielding events, creates race conditions. Solution: Make SSE generator read from database once, emit on change only. Phase 2 should clarify polling vs. event-driven strategy.

3. **JSONB schema churn:** If `output` column design changes after Phase 1, migration is messy. Phase 1 should nail down schema (e.g., all job types include `error`, `asset_count`, `started_at`, type-specific fields). Phase 5 can rely on this contract.

**Moderate:**
4. **TikTok API coverage:** Current code calls `_fetch_cover_image_url()` for image ads. Video ads may need different endpoint. Phase 4 must validate all ad type scenarios.

5. **Browser EventSource reconnection:** If connection drops, browser reconnects automatically. But does UI know which events were missed? May need last-event-id tracking or full job list fetch on reconnect.

6. **Change detection in zoneless Angular:** If frontend is migrating to zoneless (no NgZone), EventSource will not trigger change detection. Phase 3 must test with `ApplicationRef.tick()` or Signals.

**Minor:**
7. **sse-starlette version pinning:** v3.4.2 is current. If Starlette major version bumps, may need compatibility update. Monitor releases, but not blocking v1.3.

---

## Recommended Reading Order for Phases

1. **STACK-v1.3.md** — Version pinning, compatibility matrix, installation instructions
2. **This document (RESEARCH-SUMMARY-v1.3.md)** — Architecture overview, pitfalls, phase sequencing
3. **ARCHITECTURE.md** (existing, if updated for v1.3) — System component boundaries, data flow
4. **FEATURES.md** (existing, if updated for v1.3) — SuperAdmin monitoring UI requirements, job types

---

## Sources

- [sse-starlette v3.4.2 (PyPI, 2026-05-06)](https://pypi.org/project/sse-starlette/)
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette)
- [EventSource - Web APIs (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- [SQLAlchemy 2.0 JSONB Documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Angular 19 SSE using EventSource (Medium, 2026)](https://medium.com/@piyalidas.it/angular-19-sse-using-eventsource-ee770d18c7e4)
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [FastAPI + SQLAlchemy 2.0 Async Patterns (Medium)](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843)
