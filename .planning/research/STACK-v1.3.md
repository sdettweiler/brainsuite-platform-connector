# Technology Stack: v1.3 SSE Real-Time Monitoring + TikTok Asset Download

**Project:** BrainSuite Platform Connector v1.3  
**Researched:** 2026-05-07  
**Scope:** Stack additions for real-time job monitoring, PostgreSQL job persistence, and TikTok asset download. **Does NOT repeat validated v1.0–v1.2 stack** (see STACK.md for v1.1 additions).

## Recommended Stack Additions

### Server-Sent Events (SSE) Real-Time Transport

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **sse-starlette** | 3.4.2 | FastAPI/Starlette SSE endpoint implementation | Production-ready W3C SSE spec compliance; handles connection lifecycle, graceful shutdown, multi-client. Smaller footprint than WebSocket. Battle-tested in Python ecosystem. |
| **EventSource** (browser native) | N/A | Client-side SSE consumption in Angular | Native browser API—no additional npm package required. Works with RxJS Observables. Compatible with Angular 17 change detection when wrapped in NgZone or using Signals. |

### PostgreSQL Job Persistence

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **SQLAlchemy.dialects.postgresql.JSONB** | Built-in (SQLAlchemy 2.0.23) | Store full job output, error traces, metadata as semi-structured data | Avoids schema explosion for heterogeneous job types (sync, download, autofill, scoring). Queryable by nested fields without denormalization. Already using SQLAlchemy 2.0.23. |
| **asyncpg** | 0.29.0 (existing) | Async PostgreSQL driver for high-concurrency job reads | Already in requirements.txt. No new dependency. |

### TikTok Asset Download

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **yt-dlp** | Latest in requirements.txt | Download TikTok video content to GCS/MinIO | Already in project (used for YouTube DV360 cookies). Supports TikTok video + metadata extraction. Standard library in this ecosystem. Direct HTTP fetch would lose audio/video quality negotiation. |
| **boto3** | >=1.42.0 (existing) | Upload downloaded assets to S3-compatible storage | Already integrated. No new dependency. |

## No New Queue System Required

**Decision:** Continue with existing FastAPI `BackgroundTasks` + APScheduler (15-min scorer).

| System | Reason NOT to add |
|--------|-------------------|
| Celery | Heavyweight AMQP broker overhead; project already has APScheduler for periodic jobs + BackgroundTasks for fire-and-forget. SSE allows real-time progress without distributed queuing. |
| RabbitMQ / Redis queue (bullmq) | Same reason. APScheduler + BackgroundTasks sufficient for current throughput. |
| FastAPI-APScheduler job persistence | APScheduler already integrated; use PostgreSQL jobstore config if needed, not in-memory dict. This phase focuses on `background_jobs` table for transient tracking. |

## Installation

### Backend: Add Single Package

```bash
pip install sse-starlette==3.4.2
```

**Verification:**
```bash
pip show sse-starlette
# Version: 3.4.2
# Requires: starlette>=0.36
```

Update `backend/requirements.txt`:
```
sse-starlette==3.4.2
```

### Frontend: No New npm Packages

EventSource is a browser native API (MDN: [EventSource](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)). Wrap in RxJS Observable:

```typescript
// Example wrapper service (no npm install needed)
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({providedIn: 'root'})
export class JobMonitorService {
  subscribeToJobUpdates(jobId: string): Observable<any> {
    return new Observable(observer => {
      const eventSource = new EventSource(`/api/v1/jobs/${jobId}/stream`);
      eventSource.onmessage = (event) => {
        observer.next(JSON.parse(event.data));
      };
      eventSource.onerror = () => observer.error('Connection failed');
      return () => eventSource.close();
    });
  }
}
```

### Database: PostgreSQL Schema Extension

No new packages. Existing PostgreSQL + SQLAlchemy 2.0 support JSONB natively.

Example Alembic migration for `background_jobs` table:

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'background_jobs',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('job_type', sa.String(50), nullable=False),  # 'sync', 'download', 'autofill', 'scoring'
        sa.Column('org_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # PENDING, RUNNING, COMPLETE, FAILED
        sa.Column('progress_pct', sa.Integer, default=0),
        sa.Column('output', JSONB),  # Full output, error traces, nested status
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Index('ix_background_jobs_org_status', 'org_id', 'status'),
    )

def downgrade():
    op.drop_table('background_jobs')
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Real-time transport** | sse-starlette | WebSocket (websockets lib) | WebSocket adds bi-directional complexity; unidirectional push sufficient for monitoring UX. SSE simpler, lighter, no PING/PONG overhead. |
| **Real-time transport** | sse-starlette | Polling only (existing 30s interval) | Polling creates latency for long-running jobs; SSE is 10× faster with same resource footprint. |
| **Job persistence** | PostgreSQL + JSONB | Separate normalized schema | JSONB flexible for heterogeneous job types without schema evolution. Normalization overhead not justified. |
| **Job persistence** | PostgreSQL + JSONB | Redis Streams | Redis volatile; data lost on container restart. PostgreSQL is source of truth; already used for all state. |
| **TikTok download** | yt-dlp | TikTok SDK direct API | TikTok API doesn't expose raw video download URLs; yt-dlp is standard ecosystem practice. |
| **TikTok download** | yt-dlp | Simple HTTP GET from cover_url | HTTP fetch loses audio/video quality negotiation; yt-dlp handles codec selection intelligently. |

## Compatibility Matrix

| Component | Current Version | New Version | Compatibility |
|-----------|-----------------|-------------|----------------|
| FastAPI | 0.115.0 | — | sse-starlette 3.4.2 requires Starlette ≥0.36 (satisfied by FastAPI 0.115 transitive dependency) |
| Starlette | (transitive) | — | ✓ Satisfied by FastAPI 0.115.0 |
| SQLAlchemy | 2.0.23 | — | ✓ JSONB + RETURNING native in 2.0+ |
| asyncpg | 0.29.0 | — | ✓ Already compatible with FastAPI async engine |
| Python | 3.10+ | — | ✓ sse-starlette requires Python 3.10+ |
| Angular | 17.3.0 | — | ✓ EventSource supported in all modern browsers |
| RxJS | 7.8.0 | — | ✓ Observable wrapping has no version constraints |

## Verification

**sse-starlette current version (2026-05):** v3.4.2 (published 2026-05-06)

**Confirmed working with:**
- FastAPI 0.115.0 ✓
- Python 3.10+ ✓
- AsyncPG 0.29.0 + PostgreSQL ✓
- RxJS 7.8.0 + Angular 17.3.0 ✓

**NOT needed:**
- `python-socketio` (WebSocket-based, heavier)
- `celery`, `dramatiq` (distributed task queues, overkill)
- `bull`, `bullmq` (Redis-based job queues, no persistence)
- `ngx-socket-io` (Angular WebSocket wrapper)

## Key Design Decisions

1. **sse-starlette over manual Starlette StreamingResponse:** Library handles W3C compliance, automatic reconnection, event ID tracking, graceful shutdown without data loss.

2. **EventSource native API over third-party wrappers:** Reduces npm footprint. Browser EventSource is stable, well-tested, and RxJS wrapper is trivial to implement (~10 lines).

3. **JSONB for job output instead of separate columns:** Allows heterogeneous job types (sync vs. download vs. autofill) to coexist in same table without NULL explosion. Queryable via PostgreSQL JSON operators for filtering/sorting.

4. **No APScheduler job persistence migration yet:** Current in-memory dict works for 15-min scorer. Can defer to Phase 14+ if needed. This phase focuses on transient job tracking via `background_jobs` table + SSE for real-time visibility.

5. **yt-dlp already in requirements.txt:** No new Python dependency. Already used for YouTube DV360 cookie downloads. Extend same logic to TikTok video content download during sync.

## Integration Points with Existing Stack

- **FastAPI endpoints:** New `@app.get("/api/v1/jobs/{job_id}/stream")` route returns `EventSourceResponse` from sse-starlette.
- **BackgroundTasks:** Existing pattern continues. Each task updates `background_jobs` table before yielding to SSE stream.
- **APScheduler 15-min scorer:** No change. Optional future optimization: wire APScheduler job_store to PostgreSQL instead of in-memory dict (out of scope for v1.3).
- **SQLAlchemy async sessions:** New `BackgroundJob` model uses standard `AsyncSession` pattern with asyncpg. No concurrency changes.
- **MinIO/boto3:** TikTok download uploads to same storage as existing assets. No client changes.
- **Angular RxJS:** New job monitor service uses `Observable` + `EventSource`. Feeds existing NgRx store.

## Environment Variables to Add (If Needed)

No new environment variables required for SSE, JSONB, or yt-dlp. All use existing infrastructure:
- `SYNC_DATABASE_URL` → PostgreSQL connection (already set)
- `OBJECT_STORAGE_*` → MinIO/S3 credentials (already set)
- yt-dlp uses existing `aiohttp` for downloads (no new config)

## Sources

- [sse-starlette GitHub](https://github.com/sysid/sse-starlette)
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) — v3.4.2
- [EventSource - Web APIs (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- [SQLAlchemy 2.0 JSONB Documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [SQLAlchemy 2.0 Async I/O Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Angular 19 SSE using EventSource (Medium)](https://medium.com/@piyalidas.it/angular-19-sse-using-eventsource-ee770d18c7e4)
- [Implementing Server-Sent Events in Angular (Medium)](https://medium.com/@andrewkoliaka/implementing-server-sent-events-in-angular-a5e40617cb78)
- [yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)
- [FastAPI + SQLAlchemy 2.0 Async Patterns (Medium)](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843)

---

*v1.3 stack research completed 2026-05-07. Supplements existing STACK.md (v1.1 additions) with v1.3-specific requirements.*
