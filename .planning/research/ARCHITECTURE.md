# Architecture: v1.3 Job Monitoring + SSE + TikTok Asset Download

**Domain:** Multi-tenant SaaS ad intelligence platform (FastAPI + Angular + PostgreSQL)
**Researched:** 2026-05-07
**Status:** Existing architecture documented with integration points identified

## Current Architecture Overview

### Existing Components (Layers)

```
┌─────────────────────────────────────────────────────────────────┐
│  Angular 17 Frontend (port 4200)                                │
│  - HttpClient polling (30s interval) → /api/v1/notifications     │
│  - RxJS subscriptions per component                              │
│  - MatSnackBar toasts + bell icon inbox                          │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTP/REST + WebSocket (future)
┌────────────────▼────────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                     │
│  ├─ /api/v1/auth — JWT + httpOnly refresh tokens                │
│  ├─ /api/v1/platforms — OAuth handlers (Meta, TikTok, etc)      │
│  ├─ /api/v1/dashboard — unified metrics                         │
│  ├─ /api/v1/assets — creative storage + presigned URLs          │
│  ├─ /api/v1/scoring — BrainSuite integration                    │
│  ├─ /api/v1/brainsuite-config — org credentials + field mapping │
│  └─ /api/v1/super-admin — admin controls (YouTube cookies, etc) │
│                                                                   │
│  Background Tasks (async):                                       │
│  ├─ APScheduler — 15-min scoring batch + daily syncs per tz      │
│  ├─ FastAPI BackgroundTasks — ad-hoc: autofill, asset download  │
│  └─ asyncio.create_task() — fire-and-forget notifications       │
│                                                                   │
│  Database: SQLAlchemy ORM (sync engine, async sessions)          │
│  └─ Schema: multi-tenant on org_id foreign key                  │
└────────────┬──────────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────────┐
│  PostgreSQL (port 5432)                                            │
│  ├─ Auth: users, organizations, roles, refresh_tokens            │
│  ├─ Connections: platform_connections (OAuth state)              │
│  ├─ Creatives: creative_assets + asset_metadata_values            │
│  ├─ Performance: *_raw_performance tables (synced data)           │
│  ├─ Harmonization: harmonized_performance (unified view)          │
│  ├─ Scoring: creative_score_results (BrainSuite cache)           │
│  ├─ Metadata: metadata_fields + AI inference tracking            │
│  ├─ Config: org_brainsuite_config + field_mappings              │
│  ├─ Notifications: notifications (bell inbox)                    │
│  └─ System: system_config (singleton admin settings)             │
└──────────────────────────────────────────────────────────────────┘

             ┌──────────────┐
             │  Redis       │
             │  OAuth       │
             │  Sessions    │
             └──────────────┘

             ┌──────────────────┐
             │  MinIO/S3        │
             │  Creative assets │
             │  Thumbnails      │
             └──────────────────┘
```

### Existing Job Tracking (SyncJob model)

**Location:** `backend/app/models/performance.py::SyncJob`

**Current fields:**
- `platform_connection_id` — which account was synced
- `job_type` — DAILY, FULL_RESYNC, INITIAL_30D, HISTORICAL
- `status` — PENDING, RUNNING, COMPLETED, FAILED
- `started_at`, `completed_at` — timing
- `date_from`, `date_to` — sync date range
- `records_fetched`, `records_processed` — progress counters
- `error_message` — Text field for failure details
- `job_metadata` — JSONB for extensibility

**Current limitations:**
- No progress_current/progress_total (only final counts)
- No per-job output logging (full response/manifest)
- No generalized "all job types" — only platform syncs
- Instrumentation is manual (scheduler writes to DB)

---

## New Components: v1.3 Integration

### 1. Expanded Job Persistence (`background_jobs` table)

**New model:** `backend/app/models/background_job.py::BackgroundJob`

Purpose: Unified job tracking for ALL background work (syncs + scoring + downloads + autofill)

```python
class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    
    id: UUID = Column(primary_key=True)
    org_id: UUID = ForeignKey(Organization.id, nullable=False)
    job_type: str  # SYNC_DAILY, SCORE_BATCH, AUTOFILL_ASSET, TIKTOK_DOWNLOAD, etc
    status: str    # PENDING, RUNNING, COMPLETE, FAILED
    
    # Progress tracking
    progress_current: int = 0       # e.g., 45 assets scored
    progress_total: int = 0         # e.g., 200 assets to score
    
    # Timing
    started_at: DateTime = None
    ended_at: DateTime = None
    
    # Result storage
    output: dict = JSONB()          # Gemini response, manifest, error_traceback
    error_message: str = Text()     # Short error summary (<4000 chars)
    
    # Context
    metadata: dict = JSONB()        # platform, connection_id, app_type, etc
    
    created_at: DateTime = default(utcnow)
    
    __table_args__ = (
        Index("ix_background_jobs_org_status", "org_id", "status"),
        Index("ix_background_jobs_org_created", "org_id", "created_at"),
    )
```

**Relationship to SyncJob:**
- SyncJob remains for backward compatibility
- BackgroundJob is new — covers syncs + scoring + autofill + downloads
- For v1.3: both coexist; only scoring/autofill use BackgroundJob

### 2. Job Instrumentation Points

| Component | Job Type | When | Writes |
|-----------|----------|------|--------|
| scoring_job.py | SCORE_BATCH | every 15min | status, progress_current/total, output, error_message |
| ai_autofill.py | AUTOFILL_ASSET | per new asset | status, output (Gemini), error |
| tiktok_sync.py | TIKTOK_DOWNLOAD | during sync | progress, manifest of URLs |

**Key pattern:**

```python
# Release DB session before HTTP calls, then update after

async with get_session_factory()() as db:
    job = BackgroundJob(...)
    db.add(job)
    await db.flush()
    job_id = job.id

# HTTP call (no session held)
response = await poll_brainsuite_api()

async with get_session_factory()() as db:
    job = (await db.execute(select(BackgroundJob).filter_by(id=job_id))).scalar_one()
    job.status = "COMPLETE"
    job.output = response.json()
    db.add(job)
    await db.commit()
```

### 3. SSE Endpoint (`GET /api/v1/admin/jobs/stream`)

**Framework:** `sse-starlette` (pip install sse-starlette)

**Location:** `backend/app/api/v1/endpoints/admin_jobs.py` (NEW FILE)

**Endpoint signature:**

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/stream")
async def stream_jobs(
    current_superadmin = Depends(get_current_superadmin),
    db = Depends(get_db),
):
    """SSE stream of job updates.
    
    Publishes events: {"id": uuid, "org_id": uuid, "status": "RUNNING", ...}
    Connection stays open; new events pushed server→client.
    """
    async def event_generator():
        last_update = datetime.utcnow()
        while True:
            async with get_session_factory()() as db:
                jobs = await db.execute(
                    select(BackgroundJob)
                    .where(BackgroundJob.created_at >= last_update - timedelta(hours=24))
                    .order_by(BackgroundJob.created_at.desc())
                )
                for job in jobs.scalars().all():
                    yield {
                        "event": "job_update",
                        "data": json.dumps(JobResponse.from_orm(job).dict())
                    }
            
            last_update = datetime.utcnow()
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())
```

**Pydantic schema:**

```python
class JobUpdate(BaseModel):
    id: UUID
    org_id: UUID
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    error_message: Optional[str]
```

**Security:** SuperAdmin only (JWT `is_superadmin` claim required)

### 4. Angular SSE Client

**Location:** `frontend/src/app/features/admin/services/job-monitor.service.ts` (NEW)

```typescript
@Injectable({ providedIn: 'root' })
export class JobMonitorService {
  private eventSource: EventSource | null = null;
  public jobs$: BehaviorSubject<BackgroundJob[]> = new BehaviorSubject([]);
  
  connect(baseUrl: string): void {
    this.eventSource = new EventSource(`${baseUrl}/admin/jobs/stream`);
    
    this.eventSource.addEventListener('job_update', (event: MessageEvent) => {
      const job: BackgroundJob = JSON.parse(event.data);
      const jobs = this.jobs$.value;
      const idx = jobs.findIndex(j => j.id === job.id);
      
      if (idx >= 0) {
        jobs[idx] = job;
      } else {
        jobs.unshift(job);
      }
      
      this.jobs$.next(jobs);
    });
    
    this.eventSource.onerror = () => {
      this.eventSource?.close();
      setTimeout(() => this.connect(baseUrl), 5000);
    };
  }
  
  disconnect(): void {
    this.eventSource?.close();
  }
}
```

**UI Component Location:** `frontend/src/app/features/admin/components/job-monitor/`

Template shows: job list with status badges, progress bars, drill-in error detail

### 5. TikTok Asset Download Integration

**Current state:** TikTok sync fetches metadata but does NOT download files to MinIO

**New component:** `backend/app/services/sync/tiktok_asset_downloader.py`

**Integration in `tiktok_sync.py`:**

```python
async def sync_date_range(db, connection, date_from, date_to, job_id):
    # ... existing: fetch ads, upsert to tiktok_raw_performance ...
    
    # NEW: download assets
    if creative_urls:
        await download_tiktok_assets_batch(
            db, connection, creative_urls, job_id
        )
    
    return {"fetched": count, ...}
```

**What to download:**
- `video_url` → MP4 to MinIO, store presigned URL in `creative_assets.asset_url`
- `image_ids` → extract image URLs, download to MinIO
- Thumbnail: first frame of video OR first image

**Library choice:** Direct `aiohttp` (simpler, lighter); fallback to yt-dlp if needed

---

## Build Order

1. **Phase 1: Database Schema**
   - Migration: `add_background_jobs_table`
   - Add BackgroundJob model
   - Blocks: everything else

2. **Phase 2: Instrumentation Helpers**
   - `services/background_jobs.py` (create_job, update_progress)
   - `services/sync/tiktok_asset_downloader.py`
   - Depends on: Phase 1

3. **Phase 3: Service Instrumentation**
   - Modify `scoring_job.py`, `ai_autofill.py`, `tiktok_sync.py`
   - Depends on: Phase 2

4. **Phase 4: SSE Endpoint**
   - `api/v1/endpoints/admin_jobs.py` (GET /stream, /jobs, /jobs/{id})
   - Depends on: Phase 3

5. **Phase 5: Angular SSE Client**
   - `features/admin/services/job-monitor.service.ts`
   - `features/admin/components/job-monitor/` UI
   - Depends on: Phase 4

6. **Phase 6: Testing**
   - Integration + E2E tests
   - Depends on: Phase 5

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| DB lock during long sync | Keep transactions small; use flush() instead of commit() in loops |
| SSE connection dropout | EventSource auto-reconnect + frontend manual reconnect |
| Progress counter race | Use unique job_id; frontend dedupes by UUID |
| Scoring + rescore race | Rescore sets status=UNSCORED only if currently COMPLETE |
| TikTok download hangs | 30s timeout per asset; skip on timeout, continue batch |
| SSE memory leak | Clean context; keep 24h history only |
| Multi-tenant leak | org_id foreign key required; SuperAdmin sees all (by design) |

---

## File Changes Summary

### New Files
- `backend/app/models/background_job.py`
- `backend/app/services/background_jobs.py`
- `backend/app/services/sync/tiktok_asset_downloader.py`
- `backend/alembic/versions/{id}_add_background_jobs_table.py`
- `backend/app/api/v1/endpoints/admin_jobs.py`
- `frontend/src/app/features/admin/services/job-monitor.service.ts`
- `frontend/src/app/features/admin/components/job-monitor/job-monitor.component.ts`

### Modified Files
- `backend/app/models/__init__.py` — import BackgroundJob
- `backend/app/api/v1/__init__.py` — include admin_jobs router
- `backend/app/services/sync/scoring_job.py` — add BackgroundJob calls
- `backend/app/services/ai_autofill.py` — add BackgroundJob calls
- `backend/app/services/sync/tiktok_sync.py` — call asset_downloader

---

## Architecture Decisions Logged

| Decision | Why |
|----------|-----|
| New BackgroundJob table (not extend SyncJob) | Uniform schema for all job types; SyncJob is platform-specific |
| org_id on BackgroundJob | Multi-tenant scoping; enables future org-level quotas |
| status: PENDING/RUNNING/COMPLETE/FAILED | 4 states sufficient; avoids ambiguity of PROCESSING |
| progress_current/total (not %) | UI flexibility; raw counts queryable |
| output: JSONB (not separate table) | Keeps data together; still queryable |
| SSE (not WebSocket) | Simpler; unidirectional; no bidirectional complexity |
| Polling generator (not Redis) | Phase 1 simplicity; clear upgrade path later |
| TikTok download in sync (not manual) | Automatic gap closure; immediate autofill/scoring ready |
| Separate asset_downloader service | Reusable for other platforms (Meta, Google Ads) |
| BackgroundJob in SuperAdmin-only UI | Not exposed to regular users yet; visibility in v1.4 candidate |

