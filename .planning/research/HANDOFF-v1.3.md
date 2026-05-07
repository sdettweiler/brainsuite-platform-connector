# Implementation Handoff: v1.3 Stack + Integration Points

**For:** Requirements writer and roadmapper  
**From:** Phase 6 Research (2026-05-07)  
**Deliverables:** Exact versions, integration points, avoid-list for v1.3 milestone

---

## Stack Changes Summary

### ✅ ADD (Single Item)

```bash
# In backend/requirements.txt
sse-starlette==3.4.2
```

### ✅ USE (Already in Stack)

| Component | Version | File | Usage |
|-----------|---------|------|-------|
| SQLAlchemy JSONB | 2.0.23 | requirements.txt | Job output storage (no new package) |
| asyncpg | 0.29.0 | requirements.txt | Async job table reads (no new package) |
| yt-dlp | (latest) | requirements.txt | TikTok video download (no new package) |
| boto3 | >=1.42.0 | requirements.txt | Asset upload to MinIO (no new package) |
| EventSource | native | browser | SSE client (no npm install) |
| RxJS | 7.8.0 | frontend/package.json | EventSource wrapper (no new package) |
| Angular Material | 17.3.0 | frontend/package.json | Monitoring UI components (no new package) |

### ❌ DO NOT ADD

| Library | Why Not |
|---------|---------|
| celery | BackgroundTasks + APScheduler sufficient |
| websockets / python-socketio | SSE is simpler, unidirectional |
| redis-py queue / bullmq | PostgreSQL + JSONB avoids Redis volatility |
| apscheduler-persistent-jobstore | Not this phase; in-memory dict works |
| ngx-socket-io / rxjs-websockets | Use native EventSource + RxJS Observable |

---

## Integration Points by Feature

### 1. Real-Time Job Monitoring (SSE)

**Backend (FastAPI):**
- New endpoint: `GET /api/v1/jobs/{job_id}/stream` → returns `EventSourceResponse`
- Dependency: `from sse_starlette import EventSourceResponse`
- Event format: `{"data": "{\"status\": \"RUNNING\", \"progress_pct\": 50}"}`
- Source: Query `background_jobs` table, yield updates until status in (COMPLETE, FAILED)

**Frontend (Angular):**
- New service: `JobMonitorService` wraps EventSource in RxJS Observable
- Component: SuperAdmin monitoring panel subscribes via `jobMonitorService.subscribeToJobUpdates(jobId)`
- No npm changes — use browser EventSource API directly

**Example Code (Backend):**
```python
from sse_starlette import EventSourceResponse

@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_updates(job_id: str, session: AsyncSession = Depends(get_db)):
    async def generate():
        while True:
            job = await session.execute(
                select(BackgroundJob).where(BackgroundJob.id == job_id)
            )
            job_row = job.scalar_one_or_none()
            if not job_row:
                break
            yield {"data": json.dumps({
                "status": job_row.status,
                "progress_pct": job_row.progress_pct,
                "output": job_row.output,  # Full JSONB output
            })}
            if job_row.status in ("COMPLETE", "FAILED"):
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(generate())
```

**Example Code (Frontend):**
```typescript
@Injectable({providedIn: 'root'})
export class JobMonitorService {
  subscribeToJobUpdates(jobId: string): Observable<{status: string; progress_pct: number}> {
    return new Observable(observer => {
      const eventSource = new EventSource(`/api/v1/jobs/${jobId}/stream`);
      eventSource.onmessage = (event) => {
        observer.next(JSON.parse(event.data));
      };
      eventSource.onerror = () => {
        observer.error(new Error('SSE connection failed'));
      };
      return () => eventSource.close();
    });
  }
}
```

---

### 2. PostgreSQL Job Persistence (JSONB)

**Schema (Alembic migration):**
```python
from sqlalchemy.dialects.postgresql import JSONB

op.create_table(
    'background_jobs',
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('job_type', sa.String(50), nullable=False),
    sa.Column('org_id', sa.String(100), nullable=False),
    sa.Column('status', sa.String(20), nullable=False),
    sa.Column('progress_pct', sa.Integer, default=0),
    sa.Column('output', JSONB),  # Full job output
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    sa.Index('ix_background_jobs_org_status', 'org_id', 'status'),
)
```

**ORM Model:**
```python
from sqlalchemy.dialects.postgresql import JSONB

class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50))  # 'sync', 'download', 'autofill', 'scoring'
    org_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20))  # PENDING, RUNNING, COMPLETE, FAILED
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict] = mapped_column(JSONB, nullable=True)  # Full output as dict
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

**Update Pattern (in existing BackgroundTask handlers):**
```python
# During sync/download/autofill/scoring job:
job_record = await session.execute(
    select(BackgroundJob).where(BackgroundJob.id == job_id)
).scalar_one()

job_record.status = "RUNNING"
job_record.progress_pct = 25
job_record.output = {
    "asset_count": 45,
    "error": None,
    "started_at": datetime.now().isoformat(),
}
session.add(job_record)
await session.commit()

# ... do work ...

job_record.progress_pct = 100
job_record.status = "COMPLETE"
job_record.output["completed_at"] = datetime.now().isoformat()
session.add(job_record)
await session.commit()
```

**Query patterns (Phase 5 can leverage):**
```python
# Find all failed jobs with errors
await session.execute(
    select(BackgroundJob)
    .where((BackgroundJob.status == "FAILED") & (BackgroundJob.output["error"].astext != None))
)

# Find jobs by type for org
await session.execute(
    select(BackgroundJob)
    .where((BackgroundJob.org_id == org_id) & (BackgroundJob.job_type == "sync"))
    .order_by(BackgroundJob.updated_at.desc())
)
```

---

### 3. TikTok Video Asset Download

**Current Status:**
- `_fetch_cover_image_url()` fetches cover image URL via TikTok API ✓
- `_download_tiktok_thumbnail()` downloads cover image to MinIO ✓
- **MISSING:** Download actual video content (not just cover) to MinIO

**Extension Points:**
- Location: `backend/app/services/sync/tiktok_sync.py`
- Method to extend: Add `_download_tiktok_video()` alongside existing `_download_tiktok_thumbnail()`
- Implementation: Use yt-dlp (already in requirements.txt)

**Example Code:**
```python
import yt_dlp
import io

async def _download_tiktok_video(
    self,
    video_url: str,  # e.g. https://www.tiktok.com/@user/video/123456789
    org_id: str,
    ad_id: str,
) -> Optional[str]:
    """Download TikTok video via yt-dlp and upload to MinIO."""
    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()
    
    filename = f"tiktok_video_{ad_id}.mp4"
    relative_path = f"creatives/{org_id}/{filename}"
    
    # Check if already downloaded
    if obj_storage.file_exists(relative_path):
        return obj_storage.served_url(relative_path)
    
    try:
        # Download with yt-dlp (in-memory)
        ydl_opts = {
            'format': 'best[ext=mp4]',  # Best MP4
            'quiet': False,
            'no_warnings': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_url = info['url']  # Get direct download URL
        
        # Fetch video bytes
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
        
        # Upload to MinIO
        obj_storage.upload_blob(relative_path, resp.content, content_type='video/mp4')
        return obj_storage.served_url(relative_path)
    
    except Exception as e:
        logger.error(f"Failed to download TikTok video {ad_id}: {e}")
        return None
```

**Integration into sync:**
- Call `_download_tiktok_video()` in the loop where assets are processed
- Store returned URL in `TikTokRawPerformance.asset_url` (or create new column if needed)
- Emit progress to `background_jobs` table for SSE stream

---

## Validation Checklist for Phase Completion

### Phase 1: PostgreSQL Job Persistence
- [ ] Alembic migration runs without error
- [ ] `BackgroundJob` model queries return results
- [ ] JSONB output column accepts dict with `{error, asset_count, started_at, etc.}`
- [ ] Index on `(org_id, status)` improves query performance

### Phase 2: SSE Backend
- [ ] `sse-starlette==3.4.2` installed in Docker
- [ ] `/api/v1/jobs/{job_id}/stream` endpoint returns EventSourceResponse
- [ ] curl -N test shows events: `curl -N http://localhost:8000/api/v1/jobs/test123/stream`
- [ ] Events include status, progress_pct, output fields
- [ ] Connection closes gracefully when job completes

### Phase 3: EventSource Client
- [ ] JobMonitorService compiles without errors
- [ ] Subscribe call opens EventSource, receives messages
- [ ] Angular change detection works (NgZone or zoneless compatible)
- [ ] Unsubscribe closes connection

### Phase 4: TikTok Download
- [ ] yt-dlp successfully downloads TikTok video (non-DRM)
- [ ] Downloaded video uploaded to MinIO
- [ ] Video URL returned and stored in asset record
- [ ] SSE endpoint tracks progress during download

### Phase 5: SuperAdmin Monitoring UI
- [ ] `/configuration/admin` monitoring tab displays active jobs
- [ ] Job list updates in real-time via SSE
- [ ] Expand-to-detail shows full JSONB output
- [ ] Error jobs show traceback from output.error field

---

## Deployment Notes

### Docker Compose Changes
- Add `sse-starlette==3.4.2` to `backend/requirements.txt`
- No other Docker changes needed (PostgreSQL, asyncpg, yt-dlp already present)

### Environment Variables
- No new env vars required
- Existing `SYNC_DATABASE_URL`, `OBJECT_STORAGE_*` sufficient

### Backward Compatibility
- `background_jobs` table is new — no migrations of existing tables
- Existing sync/download/autofill/scoring jobs continue to work without changes
- Frontend can optionally wire SuperAdmin monitoring panel (not required for other users)

---

## References

- **STACK-v1.3.md** — Version pinning details, alternatives considered, compatibility matrix
- **RESEARCH-SUMMARY-v1.3.md** — Architecture overview, pitfalls, phase sequencing
- **sse-starlette docs:** https://github.com/sysid/sse-starlette
- **SQLAlchemy JSONB:** https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- **EventSource API:** https://developer.mozilla.org/en-US/docs/Web/API/EventSource
- **yt-dlp GitHub:** https://github.com/yt-dlp/yt-dlp

---

*Prepared for v1.3 roadmapper. See RESEARCH-SUMMARY-v1.3.md for phase sequencing and STACK-v1.3.md for full technology analysis.*
