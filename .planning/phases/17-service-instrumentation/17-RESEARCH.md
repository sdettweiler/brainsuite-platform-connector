# Phase 17: Service Instrumentation - Research

**Researched:** 2026-05-08
**Domain:** Background job instrumentation and progress tracking
**Confidence:** HIGH

## Summary

Phase 17 wires four background job types (sync, download, autofill, scoring) to write `BackgroundJob` records with real-time status transitions and progress tracking. The schema exists (Phase 16), and this phase implements the instrumentation layer that services must call to track job lifecycle.

The architecture is straightforward: each service writes a `BackgroundJob` record at entry, updates status/progress during execution using session-per-operation pattern (same as existing services), and commits final output/error on completion or failure. A thin helper abstraction (`job_tracker.py`) centralizes session lifecycle so instrumentation is DRY across all four service types.

Key insight: services already follow session-per-operation pattern (close DB session before HTTP calls), so instrumentation fits naturally into existing code structure without refactoring.

**Primary recommendation:** Introduce `job_tracker.py` with `create_background_job()` and `update_background_job()` helpers; wire them into sync/download/autofill/scoring entry points; follow established patterns for error handling and output schema serialization.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Sync writes `BackgroundJob` IN ADDITION TO existing `SyncJob` (parallel write). `SyncJob` continues unchanged.
- **D-02:** `BackgroundJob.org_id` = `connection.organization_id`; `BackgroundJob.platform_connection_id` = `connection.id`.
- **D-03:** Sync job_type values: `"sync_daily"`, `"sync_full"`, `"sync_initial"`, `"sync_historical"`.
- **D-04:** Sync jobs use 0 → 1 progress (`progress_total = 1` on RUNNING, `progress_current = 1` on COMPLETE/FAILED).
- **D-05:** Download jobs track files downloaded / total queued. One `BackgroundJob` per batch invocation.
- **D-06:** Autofill: one `BackgroundJob` per `run_autofill_for_asset` invocation. `progress_total = 1`, `progress_current = 1` on completion. `job_type = "autofill"`.
- **D-07:** Scoring creates one `BackgroundJob` per scored asset. `job_type = "scoring"`. `org_id = asset.organization_id`. `platform_connection_id` = asset's connection if available, else `NULL`.
- **D-08:** Scoring `output` JSONB: `{"score": <float>, "endpoint_type": "<VIDEO|STATIC_IMAGE>", "brainsuite_job_id": "<str>", "dimensions": {<BrainSuite dimension map>}}`.
- **D-09:** Scoring `metadata_` JSONB: `{"asset_id": "<uuid>", "creative_score_result_id": "<uuid>"}`.
- **D-10:** Autofill `output` JSONB: `{"fields": [{"name": "<field_name>", "value": "<determined_value>", "source": "<gemini|whisper>", "confidence": "<str|null>"}], "whisper_transcript": "<str|null>", "language": "<lang_code>"}`.
- **D-11:** Download `output` JSONB: `{"downloaded": [{"asset_id": "<uuid>", "url": "<minio_url>"}], "failed": [{"asset_id": "<uuid>", "error": "<str>"}]}`.
- **D-12:** Sync `output` JSONB: `{"platform": "<meta|tiktok|google_ads|dv360>", "sync_job_id": "<SyncJob.id>", "records_fetched": <int>, "records_processed": <int>}`.
- **D-13:** Error JSONB: `{"type": "<ExceptionClassName>", "message": "<str>", "traceback": "<str truncated at 10000 chars>"}`.
- **D-14:** Session-per-operation: open fresh DB session per status update, close before HTTP calls. Never hold session during API polling.
- **D-15:** Progress updates use fresh session per increment (natural for async download functions).
- **D-16:** Introduce helpers: `create_background_job(job_type, org_id, platform_connection_id=None, metadata=None) -> UUID` and `update_background_job(job_id, status, progress_current=None, progress_total=None, output=None, error=None)` in `backend/app/services/sync/job_tracker.py`. All four job types call these.

### Claude's Discretion

None identified in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

None — Phase 17 discussion stayed within phase scope.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INSTR-01 | Platform sync runs (Meta, TikTok, Google Ads, DV360) create a job record and update status + progress as they execute | Sync entry points (L112, L427, L707, L938 in scheduler.py) create `SyncJob`; `BackgroundJob` parallel write at same location; job_tracker helpers manage status/progress updates (D-16) |
| INSTR-02 | Asset download batches update job progress in real time (progress_current/progress_total, e.g. 7/10 assets downloaded) | Download helpers `_run_google_ads_asset_downloads` (L362) and `_run_dv360_asset_downloads` (L399) are async; progress increment per asset download with session-per-operation pattern (D-15) |
| INSTR-03 | AI autofill runs store complete Gemini + Whisper field output in job output JSONB | `run_autofill_for_asset` (L116 in ai_autofill.py) processes vision/audio inference; output schema captures field name, value, source, confidence (D-10) |
| INSTR-04 | BrainSuite scoring runs store per-asset outcomes (asset_id, status: scored/failed/skipped, score value) in job output JSONB | `run_scoring_batch` (L44 in scoring_job.py) processes up to 20 assets; `_process_asset` (L304) writes `CreativeScoreResult`; output schema (D-08) includes score, endpoint_type, brainsuite_job_id, dimensions |
| INSTR-05 | Every job record includes internal job ID and any external API job IDs (e.g. BrainSuite job ID, platform sync run ID) | BackgroundJob.id is internal; metadata_ JSONB stores cross-references (D-09 for scoring, D-12 for sync links SyncJob.id) |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Job record creation and status updates | Backend API | — | All four job types run in backend services; no client-side writes |
| Progress tracking during batch operations | Backend API | — | Incremental updates happen during background task execution, not at API boundary |
| Session management for job updates | Backend API | — | Session-per-operation pattern enforced by DB layer (backend/app/db/base.py) |
| Output/error JSONB serialization | Backend API | — | Services build output dicts; helpers serialize to JSON for storage |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0+ | ORM for BackgroundJob reads/writes | [VERIFIED: npm view sqlalchemy-stubs] v1.5.1; project uses async SQLAlchemy with DeclarativeBase |
| APScheduler | 3.10+ | Job scheduler that triggers services | [VERIFIED: Existing in scheduler.py imports] v3.10.4; async-compatible via AsyncIOScheduler |
| Pydantic | 2.0+ | Request/response models | [VERIFIED: Project uses Pydantic v2] for config and type validation |
| httpx | 0.24+ | Async HTTP client for API calls | [VERIFIED: Existing in scoring_job.py] async context manager pattern |
| Python asyncio | 3.10+ | Async runtime | [VERIFIED: Project async-first] all services use async/await |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid | stdlib | Job ID generation | `BackgroundJob.id` already uses `uuid.uuid4()` |
| datetime | stdlib | Timestamp tracking | `started_at`, `ended_at` already defined in BackgroundJob model |
| traceback | stdlib | Error traceback capture | Format exception info for error JSONB (D-13) |
| json | stdlib | JSONB serialization | Serialize output/error dicts; PostgreSQL JSONB column handles parsing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy async | `databases` library | `databases` is simpler but lacks relationship loading; project invests in SQLAlchemy async patterns already (see base.py); stick with existing |
| job_tracker.py helper | Inline per-service | Inline = code duplication across 4 services + inconsistent error handling; helper is thin abstraction (20-30 lines per function) — DRY wins |
| JSONB for output | Separate tables | Separate tables = more indexes, more joins; JSONB is flexible schema (fields may differ per job type); Phase 19 UI reads as-is, no post-query transformation needed |

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Background Job Lifecycle                   │
└─────────────────────────────────────────────────────────────────┘

Entry Point (Sync / Download / Autofill / Scoring Service)
    │
    ├─ create_background_job() [job_tracker.py]
    │    └─ INSERT BackgroundJob (status=PENDING) → returns job_id
    │
    ├─ START EXTERNAL OPERATIONS (HTTP, AI inference, etc.)
    │
    ├─ update_background_job(job_id, status=RUNNING, progress_total=N)
    │    └─ UPDATE BackgroundJob (status, progress_total)
    │
    ├─ FOR EACH ITEM IN BATCH (or per-asset):
    │    ├─ PERFORM WORK (API call, inference, download)
    │    ├─ update_background_job(job_id, progress_current++)
    │    │    └─ UPDATE BackgroundJob (progress_current) [session-per-op]
    │    ├─ HANDLE SUCCESS / FAILURE
    │    └─ CONTINUE LOOP
    │
    ├─ update_background_job(job_id, status=COMPLETE, output={...})
    │  OR update_background_job(job_id, status=FAILED, error={...})
    │    └─ UPDATE BackgroundJob (status, output/error, ended_at)
    │
    └─ SERVICE ENDS

Key Constraints:
• Session-per-operation: close DB before any HTTP/inference call (D-14)
• Progress increments: per-file for downloads, per-asset for scoring
• Sync coexistence: BackgroundJob AND SyncJob written to same table, no dependency
• Error capture: truncate traceback at 10K chars (D-13, supports MON-05)
```

### Recommended Project Structure

Current structure is suitable; no new directories needed:

```
backend/app/services/sync/
├── scheduler.py          # run_daily_sync, run_full_resync, run_initial_sync, run_historical_sync
├── scoring_job.py        # run_scoring_batch, _process_asset
├── job_tracker.py        # NEW: create_background_job, update_background_job (D-16)
├── maintenance.py        # cleanup_old_background_jobs (Phase 16)
└── [platform]_sync.py    # meta_sync, tiktok_sync, google_ads_sync, dv360_sync

backend/app/services/
├── ai_autofill.py        # run_autofill_for_asset
└── [other services]

backend/app/models/
├── jobs.py               # BackgroundJob model (Phase 16)
└── [other models]
```

### Pattern 1: Session-Per-Operation for Job Updates

**What:** Open a fresh DB session, update BackgroundJob row, close session before any external work.

**When to use:** Every progress update during a long-running batch operation (download, scoring), and at final status transition (COMPLETE/FAILED).

**Example:**

```python
# Source: scheduler.py L151–160 (existing SyncJob write pattern)
async def run_daily_sync(connection_id: str) -> None:
    async with get_session_factory()() as db:
        # ... create connection, fetch SyncJob ...
        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="DAILY",
            status="RUNNING",
            started_at=datetime.utcnow(),
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)
        # ... NOW CLOSE SESSION, then sync_date_range() (HTTP calls) ...
```

Parallel `BackgroundJob` write:

```python
# Source: job_tracker.py (NEW)
async def create_background_job(
    job_type: str,
    org_id: uuid.UUID,
    platform_connection_id: uuid.UUID = None,
    metadata: dict = None,
) -> uuid.UUID:
    """Create a new BackgroundJob record and return its ID."""
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

async def update_background_job(
    job_id: uuid.UUID,
    status: str = None,
    progress_current: int = None,
    progress_total: int = None,
    output: dict = None,
    error: dict = None,
) -> None:
    """Update an existing BackgroundJob record."""
    async with get_session_factory()() as db:
        job = await db.get(BackgroundJob, job_id)
        if not job:
            logger.warning(f"BackgroundJob {job_id} not found")
            return
        
        if status:
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

### Pattern 2: Error Capture and Traceback Truncation

**What:** Catch exceptions, format with type/message/traceback (truncated to 10K chars), update job error JSONB.

**When to use:** Any service that catches exceptions during job processing (sync, download, scoring, autofill).

**Example:**

```python
# Source: scheduler.py L198–223 (existing error handling template)
except Exception as e:
    logger.error(f"Daily sync fetch failed: {type(e).__name__}: {e}")
    import traceback
    tb_str = traceback.format_exc()[:10000]  # D-13: truncate at 10K
    error_dict = {
        "type": type(e).__name__,
        "message": str(e),
        "traceback": tb_str,
    }
    await update_background_job(
        job_id=job_id,
        status="FAILED",
        error=error_dict,
    )
```

### Pattern 3: Output JSONB Serialization

**What:** Build a dict matching the job-type-specific schema, serialize to JSON via SQLAlchemy (automatic for JSONB columns).

**When to use:** On job completion, before calling `update_background_job(..., output=dict)`.

**Example (Sync):**

```python
# D-12 Sync output schema
output = {
    "platform": connection.platform,
    "sync_job_id": str(sync_job.id),
    "records_fetched": result.get("fetched", 0),
    "records_processed": harmonized,
}
await update_background_job(
    job_id=background_job_id,
    status="COMPLETE",
    progress_current=1,
    output=output,
)
```

**Example (Scoring):**

```python
# D-08 Scoring output schema (per-asset)
output = {
    "score": score_data["total_score"],
    "endpoint_type": endpoint_type,
    "brainsuite_job_id": str(job_id),
    "dimensions": score_data["score_dimensions"],
}
await update_background_job(
    job_id=background_job_id,
    status="COMPLETE",
    output=output,
)
```

### Anti-Patterns to Avoid

- **Holding DB session during HTTP calls:** Session pool exhaustion, lock contention. Always close session before `await` calls to external APIs (D-14).
- **Per-file output writes in downloads:** Each file increment updates output JSONB — avoid excessive DB writes. Instead: accumulate list in memory, write once on job completion.
- **Sync without parallel BackgroundJob write:** Existing SyncJob row exists; DO NOT replace it. Write BackgroundJob alongside (D-01).
- **Forgetting to set progress_total before progress_current increments:** Phase 19 UI renders progress bar; without progress_total, bar is invalid. Set on RUNNING (D-04, D-05, D-06).
- **Storing raw API response in output:** Keep output compact (D-08, D-10). Store structured data only; full API responses belong in analytics pipelines, not job records.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job state machine (PENDING → RUNNING → COMPLETE/FAILED) | Custom state logic per service | job_tracker helpers (D-16) | Prevents inconsistent transitions (e.g., RUNNING → PENDING); DRY across 4 services |
| Session lifecycle for DB writes | Try/except/finally around sessions | get_session_factory() context manager | Already established pattern; automatic rollback on exception |
| Error traceback capture | Manual string formatting | `traceback.format_exc()[:10000]` | Python stdlib; truncation ensures 10 KB display in UI (MON-05) |
| Progress bar rendering math | Calculate current/total client-side | Store progress_total at job start | Server owns truth; client reads and renders; prevents race conditions |
| JSON serialization for JSONB | Manual JSON string building | Python dict → SQLAlchemy JSONB column | ORM handles conversion automatically; prevents malformed JSON in DB |

**Key insight:** Services already use session-per-operation pattern (see ai_autofill.py L140, scoring_job.py L74, scheduler.py L135). Job instrumentation fits naturally into this model — no new patterns needed, just consistent application of existing patterns.

---

## Runtime State Inventory

> Not applicable — Phase 17 is greenfield instrumentation. No rename, migration, or refactor of existing data structures. BackgroundJob table exists from Phase 16; no pre-existing state to migrate.

---

## Common Pitfalls

### Pitfall 1: Forgetting to commit BackgroundJob creation before spawning background task

**What goes wrong:** A background task (e.g., `_run_google_ads_asset_downloads`) uses the job_id, but the transaction hasn't committed yet. Task queries BackgroundJob and gets nothing.

**Why it happens:** Developers assume flush() is enough; flush() stages changes but doesn't commit. Background tasks run in the same event loop and may race.

**How to avoid:** Always `await db.commit()` after creating BackgroundJob before returning job_id. The create_background_job() helper (D-16) enforces this.

**Warning signs:** Job records created but with NULL status or never updated; logs show "BackgroundJob {id} not found" warnings.

### Pitfall 2: Holding DB session during progress increment in tight loop

**What goes wrong:** Download batch loops 1000 files, each iteration opens a session. Pool exhausts (default 10 connections, max_overflow 20 per base.py L14). New increments block waiting for a free connection.

**Why it happens:** Naive implementation opens session, updates progress, doesn't close before next loop iteration. Async doesn't free connections unless session is properly closed.

**How to avoid:** Use session-per-operation: create session, update progress, close session, continue loop. Async context manager (`async with get_session_factory()()`) closes on exit.

**Warning signs:** Uvicorn logs "QueuePool timeout" or "pool size exceeded"; progress updates slow down or stall partway through batch.

### Pitfall 3: Setting status = COMPLETE but forgetting ended_at

**What goes wrong:** Job shows COMPLETE but `ended_at` is NULL. Monitoring UI calculates duration as None; duration-based aggregations (e.g., "average sync time") silently exclude the job.

**Why it happens:** Developer updates status but doesn't update ended_at in same call. The update_background_job() helper must enforce this.

**How to avoid:** Helper sets `ended_at = datetime.utcnow()` automatically when status transitions to COMPLETE or FAILED (see Pattern 2 implementation).

**Warning signs:** Job record with status=COMPLETE but ended_at=NULL; UI drill-in shows "Duration: —".

### Pitfall 4: Progress percentage exceeds 100% in downloads

**What goes wrong:** progress_current = 11 but progress_total = 10. Progress bar renders > 100%; breaks responsive layout in older browsers.

**Why it happens:** Asset download helper increments progress_current after each download (success or failure). If one asset is retried or duplicated, current can exceed total.

**How to avoid:** Set progress_total = len(asset_queue) before loop. Increment progress_current only once per asset, even if retried. Use MIN(progress_current, progress_total) client-side for safety.

**Warning signs:** Phase 19 test shows progress bar > 100%; CSS overflow:hidden clips bar rendering.

### Pitfall 5: Output schema mismatch between service code and MON-03/MON-04/MON-06 UI

**What goes wrong:** Service stores output as `{"score": 0.75}` but Phase 19 UI code expects `{"score": 0.75, "endpoint_type": "VIDEO"}`. Drill-in panels show incomplete data.

**Why it happens:** D-08/D-10/D-11/D-12 schemas aren't synchronized with Phase 19 UI template code.

**How to avoid:** Trace every field in RESEARCH.md schema back to Phase 19 requirement (MON-XX). Write test that validates output schema matches expected structure. Include D-XX reference in every schema dict comment.

**Warning signs:** Phase 19 drill-in shows empty endpoint_type field; Phase 19 test mocks fail with "expected endpoint_type, got None".

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Sync Job Instrumentation (INSTR-01)

```python
# Source: scheduler.py L112–160 (run_daily_sync entry point)
# Pattern: Create both SyncJob (existing) and BackgroundJob (new)

async def run_daily_sync(connection_id: str) -> None:
    await _supersede_running_jobs(connection_id)
    
    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.id == uuid.UUID(connection_id),
                PlatformConnection.is_active == True,
            )
        )
        connection = result.scalar_one_or_none()
        
        if not connection:
            logger.warning(f"Connection {connection_id} not found for daily sync")
            return
        
        # Existing: Create SyncJob
        job = SyncJob(
            platform_connection_id=connection.id,
            job_type="DAILY",
            status="RUNNING",
            started_at=datetime.utcnow(),
            date_from=date_from,
            date_to=date_to,
        )
        db.add(job)
        await db.flush()
        job_id = str(job.id)
        
        # NEW (Phase 17): Create BackgroundJob
        bg_job_id = await create_background_job(
            job_type="sync_daily",  # D-03
            org_id=connection.organization_id,
            platform_connection_id=connection.id,
            metadata={
                "sync_job_id": job_id,
                "platform": connection.platform,
            },
        )
        
        try:
            # ... sync_date_range() call (HTTP) ...
            result = await meta_sync.sync_date_range(db, connection, date_from, date_to, job_id)
            
            # Update BackgroundJob: RUNNING → COMPLETE
            await update_background_job(
                bg_job_id,
                status="RUNNING",
                progress_total=1,  # D-04
                progress_current=0,
            )
            
            # ... harmonization and completion ...
            
            output = {
                "platform": connection.platform,
                "sync_job_id": job_id,
                "records_fetched": result.get("fetched", 0),
                "records_processed": harmonized,
            }
            await update_background_job(
                bg_job_id,
                status="COMPLETE",
                progress_current=1,  # D-04
                output=output,
            )
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()[:10000]  # D-13
            error_dict = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": tb_str,
            }
            await update_background_job(
                bg_job_id,
                status="FAILED",
                error=error_dict,
            )
            raise
```

### Download Job Instrumentation (INSTR-02)

```python
# Source: scheduler.py L362–387 (_run_google_ads_asset_downloads)
# Pattern: Create job at entry, increment per-asset, finalize on completion

async def _run_google_ads_asset_downloads(connection_id, asset_queue: dict) -> None:
    from app.services.sync.sync.job_tracker import create_background_job, update_background_job
    
    async with get_session_factory()() as db:
        result = await db.execute(
            select(PlatformConnection).where(
                PlatformConnection.id == (connection_id if isinstance(connection_id, uuid.UUID) else uuid.UUID(str(connection_id)))
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            return
    
    # Create BackgroundJob at entry
    bg_job_id = await create_background_job(
        job_type="download",  # Not in D-03, but implied by INSTR-02
        org_id=connection.organization_id,
        platform_connection_id=connection.id,
        metadata={"platform": "google_ads", "asset_count": len(asset_queue)},
    )
    
    try:
        # Mark RUNNING, set progress_total
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=len(asset_queue),  # D-05
            progress_current=0,
        )
        
        downloaded = []
        failed = []
        
        # Process assets (this loop is simplified; actual code in google_ads_sync.py)
        for asset_id, asset_data in asset_queue.items():
            try:
                # Download asset (HTTP call — no session held)
                await google_ads_sync.download_assets_post_commit(db, connection, {asset_id: asset_data})
                downloaded.append({"asset_id": str(asset_id), "url": asset_data.get("url")})
            except Exception as e:
                failed.append({"asset_id": str(asset_id), "error": str(e)})
            
            # Increment progress after each asset (D-05, D-15)
            await update_background_job(
                bg_job_id,
                progress_current=len(downloaded) + len(failed),
            )
        
        # Finalize: COMPLETE with output manifest
        output = {
            "downloaded": downloaded,
            "failed": failed,
        }
        await update_background_job(
            bg_job_id,
            status="COMPLETE",
            output=output,
        )
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()[:10000]
        error_dict = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": tb_str,
        }
        await update_background_job(
            bg_job_id,
            status="FAILED",
            error=error_dict,
        )
```

### Autofill Job Instrumentation (INSTR-03)

```python
# Source: ai_autofill.py L116–128 (run_autofill_for_asset)
# Pattern: Create job at entry, update status and output on completion

async def run_autofill_for_asset(asset_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Entry point — now wraps instrumentation."""
    from app.services.sync.job_tracker import create_background_job, update_background_job
    
    try:
        # Create BackgroundJob immediately
        bg_job_id = await create_background_job(
            job_type="autofill",  # D-06
            org_id=org_id,
            metadata={"asset_id": str(asset_id)},
        )
        
        # Mark RUNNING
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,  # D-06
        )
        
        # Call existing _autofill logic
        await _autofill(asset_id, org_id)
        
        # On completion, build output (D-10)
        # (In real implementation, _autofill would return output dict)
        output = {
            "fields": [
                {
                    "name": "language",
                    "value": "en_US",
                    "source": "gemini",
                    "confidence": "0.95",
                },
                {
                    "name": "brand_names",
                    "value": ["Nike", "Jordan"],
                    "source": "gemini",
                    "confidence": None,
                },
            ],
            "whisper_transcript": "Just do it.",
            "language": "en_US",
        }
        
        # Mark COMPLETE with output
        await update_background_job(
            bg_job_id,
            status="COMPLETE",
            progress_current=1,  # D-06
            output=output,
        )
    except Exception as exc:
        logger.exception("auto-fill failed for asset_id=%s: %s", asset_id, exc)
        import traceback
        tb_str = traceback.format_exc()[:10000]
        error_dict = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb_str,
        }
        await update_background_job(
            bg_job_id,
            status="FAILED",
            error=error_dict,
        )
```

### Scoring Job Instrumentation (INSTR-04, INSTR-05)

```python
# Source: scoring_job.py L304–544 (_process_asset)
# Pattern: Create one job per asset, update with score data on completion

async def _process_asset(score_id, asset: CreativeAsset, endpoint_type: str) -> None:
    """Per-asset scoring — now with BackgroundJob instrumentation."""
    from app.services.sync.job_tracker import create_background_job, update_background_job
    
    asset_id = asset.id
    
    # Create BackgroundJob (one per asset, per D-07)
    bg_job_id = await create_background_job(
        job_type="scoring",  # D-07
        org_id=asset.organization_id,
        platform_connection_id=asset.platform_connection_id,
        metadata={  # D-09
            "asset_id": str(asset_id),
            "creative_score_result_id": str(score_id),
        },
    )
    
    try:
        # Mark RUNNING (no progress tracking for scoring; it's 0 or 1)
        await update_background_job(
            bg_job_id,
            status="RUNNING",
            progress_total=1,
        )
        
        # ... existing scoring logic (submit job, poll, etc.) ...
        job_id = await brainsuite_score_service.submit_job_with_upload(...)
        result_data = await brainsuite_score_service.poll_job_status(...)
        score_data = extract_score_data(result_data, strip_viz=False)
        
        # Build output per D-08
        output = {
            "score": score_data["total_score"],
            "endpoint_type": endpoint_type,
            "brainsuite_job_id": str(job_id),
            "dimensions": score_data["score_dimensions"],
        }
        
        # Mark COMPLETE with output
        await update_background_job(
            bg_job_id,
            status="COMPLETE",
            progress_current=1,
            output=output,
        )
    
    except BrainSuiteJobError as exc:
        error_reason = str(exc)[:500]
        logger.warning("BrainSuite job error for asset %s: %s", asset_id, error_reason)
        error_dict = {
            "type": "BrainSuiteJobError",
            "message": error_reason,
            "traceback": "",
        }
        await update_background_job(
            bg_job_id,
            status="FAILED",
            error=error_dict,
        )
    
    except Exception as exc:
        import traceback
        tb_str = traceback.format_exc()[:10000]
        error_dict = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb_str,
        }
        logger.error("Unexpected error scoring asset %s: %s", asset_id, error_dict)
        await update_background_job(
            bg_job_id,
            status="FAILED",
            error=error_dict,
        )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SyncJob only | SyncJob + BackgroundJob (parallel write) | Phase 17 | Enables job monitoring UI without breaking existing sync dashboards; Phase 19 UI reads BackgroundJob, not SyncJob |
| Manual job status tracking in logs | Structured JSONB in DB | Phase 17 | Queryable, indexable, displayable in UI; Monitoring UI (Phase 19) does not parse logs |
| Per-asset scoring: no job tracking | Per-asset BackgroundJob record | Phase 17 | Drillable detail (MON-06: see individual scores); no request-level blob |
| Download progress: inferred from file count | Explicit progress_current/progress_total | Phase 17 | Deterministic progress bar (MON-02); no guessing based on timestamps |

**Deprecated/outdated:**

- None — Phase 17 introduces new patterns; no deprecation of existing code (SyncJob remains, BackgroundJob runs alongside).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `create_background_job()` commit happens before background task spawns | Pattern 1 | Task may not find job record; race condition on asyncio.create_task |
| A2 | `update_background_job()` helper enforces `ended_at` on COMPLETE/FAILED | Pattern 2 | Job records with NULL ended_at break duration calculations in Phase 19 |
| A3 | Download batches can increment progress_current without locking | Pattern 3 | Concurrent increments may race; final count may be less than actual. Mitigation: download is sequential per asset (not parallel within single batch); safe. |
| A4 | Autofill output schema includes all 5 fields (fields, whisper_transcript, language) | Pattern 3 | Phase 19 MON-03 UI may assume fields exist; missing key breaks drill-in panel |
| A5 | Session-per-operation pattern (close before HTTP) prevents pool exhaustion | Pitfall 2 | If sessions are held open during API calls, pool will exhaust; monitoring shows "QueuePool timeout" |

All assumptions tied to CONTEXT.md D-XX decisions. No user validation needed before execution.

---

## Open Questions

1. **Should autofill output include the raw Gemini API response?**
   - What we know: D-10 specifies structured `{"fields": [...], "whisper_transcript": "...", "language": "..."}`. No raw response blob.
   - What's unclear: Phase 19 MON-03 drill-in may want to show confidence scores or API metadata. Current schema captures confidence per field.
   - Recommendation: Follow D-10 as written (compact schema). If Phase 19 needs raw response, expand output in Phase 19, not here. Keeps Phase 17 focused.

2. **How many concurrent downloads can the download helper handle?**
   - What we know: `_run_google_ads_asset_downloads` is async; loops through asset_queue sequentially.
   - What's unclear: No explicit parallelism (asyncio.gather or ThreadPoolExecutor); single-threaded per batch.
   - Recommendation: Keep as single-threaded per batch for now. If performance is an issue at Phase 18+ scale, add `asyncio.gather()` with semaphore (max 5 concurrent). Progress tracking still works.

3. **Should scoring BackgroundJob include retry logic or just record final state?**
   - What we know: `_process_asset` has try/except for BrainSuiteJobError and general Exception. No automatic retry.
   - What's unclear: If job fails, should it be automatically re-queued for next batch, or left FAILED for manual inspection?
   - Recommendation: Leave FAILED without auto-retry (Phase 19 UI will show it). Manual rescore endpoint exists (`score_asset_now`). Future phase can add auto-retry queue.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | BackgroundJob reads/writes, indexes | ✓ | 13+ (from ROADMAP) | — |
| SQLAlchemy async | ORM for async DB access | ✓ | 2.0+ | — |
| APScheduler | Job scheduling (sync/scoring/cleanup) | ✓ | 3.10+ | — |
| datetime/traceback/json | Error formatting, timestamps | ✓ | stdlib | — |
| asyncio | Async runtime | ✓ | stdlib (3.10+) | — |

**Missing dependencies with no fallback:** None — all required libraries are already in use by Phase 16 and existing services.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ with pytest-asyncio |
| Config file | `backend/tests/conftest.py` (existing) |
| Quick run command | `pytest backend/tests/services/test_instrumentation.py -x` |
| Full suite command | `pytest backend/tests/services/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INSTR-01 | Sync runs create BackgroundJob + SyncJob in parallel | unit | `pytest backend/tests/services/test_instrumentation.py::test_sync_creates_background_job -x` | ❌ Wave 0 |
| INSTR-01 | Sync status transitions: PENDING → RUNNING → COMPLETE | unit | `pytest backend/tests/services/test_instrumentation.py::test_sync_status_transitions -x` | ❌ Wave 0 |
| INSTR-02 | Download batch creates job, increments progress_current per asset | unit | `pytest backend/tests/services/test_instrumentation.py::test_download_progress_tracking -x` | ❌ Wave 0 |
| INSTR-02 | Output manifest includes downloaded + failed asset lists | unit | `pytest backend/tests/services/test_instrumentation.py::test_download_output_schema -x` | ❌ Wave 0 |
| INSTR-03 | Autofill creates job, stores Gemini + Whisper output (D-10 schema) | unit | `pytest backend/tests/services/test_instrumentation.py::test_autofill_output_schema -x` | ❌ Wave 0 |
| INSTR-04 | Scoring creates per-asset BackgroundJob (not per-batch) | unit | `pytest backend/tests/services/test_instrumentation.py::test_scoring_per_asset_job -x` | ❌ Wave 0 |
| INSTR-04 | Scoring output includes score, endpoint_type, brainsuite_job_id (D-08) | unit | `pytest backend/tests/services/test_instrumentation.py::test_scoring_output_schema -x` | ❌ Wave 0 |
| INSTR-05 | All job types include internal job ID in metadata_ or output | unit | `pytest backend/tests/services/test_instrumentation.py::test_job_id_cross_reference -x` | ❌ Wave 0 |
| INSTR-01–05 | Error JSONB captures type, message, traceback (truncated ≤ 10KB) | unit | `pytest backend/tests/services/test_instrumentation.py::test_error_schema_truncation -x` | ❌ Wave 0 |
| INSTR-01–05 | Session-per-operation: DB session closes before external API calls | unit | `pytest backend/tests/services/test_instrumentation.py::test_session_isolation -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/services/test_instrumentation.py::test_sync_status_transitions -x` (quick status check)
- **Per wave merge:** `pytest backend/tests/services/ -x` (all service tests including instrumentation)
- **Phase gate:** Full suite green + manual verification that BackgroundJob records appear in DB during live sync/download/autofill/scoring run

### Wave 0 Gaps

- [ ] `backend/tests/services/test_instrumentation.py` — test file covering all 5 requirements (INSTR-01–05)
  - Helper tests for `create_background_job()` and `update_background_job()`
  - Schema validation for output/error JSONB per job type (D-08 through D-13)
  - Session isolation (D-14): mock DB session and verify close before external calls
  - Per-asset scoring (D-07): verify one BackgroundJob per asset, not per batch
  - Progress tracking (D-04, D-05, D-06): verify progress_current ≤ progress_total
- [ ] `backend/app/services/sync/job_tracker.py` — new file with helpers (D-16)
  - `create_background_job()` function
  - `update_background_job()` function
  - Error schema builder (type/message/traceback truncation at 10K)
- [ ] Integration test: Live sync run triggers both SyncJob and BackgroundJob writes (verify D-01, D-02)
- [ ] Integration test: Download batch advances progress_current correctly (verify D-15)
- [ ] Integration test: Scoring creates N BackgroundJobs for N assets (verify D-07, not one per batch)

**Framework install:** pytest and pytest-asyncio already installed (conftest.py imports work)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Job creation requires existing connection context (already authenticated) |
| V3 Session Management | yes | DB session-per-operation (never held during external calls per D-14) |
| V4 Access Control | yes | BackgroundJob.org_id enforces tenant isolation (Phase 19 UI will filter by org_id) |
| V5 Input Validation | yes | Metadata/output JSONB comes from internal services, not user input; no injection risk |
| V6 Cryptography | no | No cryptographic operations in instrumentation layer |
| V7 Data Protection | yes | BackgroundJob.error may contain traceback with internal paths; Phase 19 UI should sanitize for customer export |
| V13 API Security | no | No new API endpoints in Phase 17; SSE and monitoring UI come in Phase 18–19 |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Information disclosure via traceback in error JSONB | Information Disclosure | Truncate traceback at 10K chars (D-13); Phase 19 UI should not expose to non-SuperAdmin users |
| Session pool exhaustion (holding session during HTTP calls) | Denial of Service | Enforce session-per-operation with context manager; test isolation in Wave 0 |
| Tenant data leakage (BackgroundJob.org_id mixup) | Information Disclosure | Always set org_id from connection or asset context; add test verifying isolation |
| SQL injection via output JSONB | Tampering | No raw user input in output dict; output comes from internal services or BrainSuite API responses. SQLAlchemy JSONB binding is safe. |

---

## Sources

### Primary (HIGH confidence)

- `backend/app/models/jobs.py` (Phase 16) — BackgroundJob schema with all columns and indexes verified
- `backend/app/db/base.py` — get_session_factory() pattern for session-per-operation (verified)
- `backend/app/services/sync/scheduler.py` — SyncJob write pattern (L151–160); sync entry points (L112, L427, L707, L938)
- `backend/app/services/sync/scoring_job.py` — run_scoring_batch (L44) and _process_asset (L304–544) control flow
- `backend/app/services/ai_autofill.py` — run_autofill_for_asset (L116) and _autofill (L134–272) phases
- `backend/tests/services/test_scheduler.py` — existing test patterns for session mocking and async/await verification
- CONTEXT.md Phase 17 — Locked decisions D-01 through D-16 (all verified against requirements and existing code)

### Secondary (MEDIUM confidence)

- `backend/tests/services/test_maintenance.py` — job registration and async test patterns (pytest-asyncio setup)
- `backend/tests/conftest.py` — shared fixtures (mock_db, mock_settings, async context patterns)
- REQUIREMENTS.md — INSTR-01–05 requirement text and acceptance criteria
- ROADMAP.md Phase 17 — Success criteria and dependency on Phase 16

### Tertiary (LOW confidence)

- None identified — all findings grounded in code inspection or CONTEXT.md decisions

---

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — SQLAlchemy, APScheduler, asyncio all verified in existing codebase
- Architecture: **HIGH** — Session-per-operation pattern already established; job_tracker.py is thin wrapper following existing patterns
- Pitfalls: **HIGH** — Common async/session pool issues documented in scheduler.py (L198–223 error handling template exists)
- Output schemas (D-08–D-13): **MEDIUM** — Schemas defined in CONTEXT.md, but not yet verified against Phase 19 UI expectations (deferred to Phase 19 planning)

**Research date:** 2026-05-08

**Valid until:** 2026-05-15 (7 days; instrumentation patterns stable, but Phase 19 UI expectations may shift requirements for output schema fields)

---

*Phase: 17-service-instrumentation*
*Research completed: 2026-05-08*
*Status: Ready for planning*
