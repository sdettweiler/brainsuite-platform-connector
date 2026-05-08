# Phase 17: Service Instrumentation - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire all four background job types (sync, download, autofill, scoring) to write `BackgroundJob` records with PENDING → RUNNING → COMPLETE/FAILED status transitions, progress tracking, structured output JSONB, and error JSONB throughout execution.

This phase does NOT build any UI, SSE transport, or new API endpoints. It is purely backend instrumentation. The `background_jobs` table and cleanup job are already in place (Phase 16). The `BackgroundJob` model is importable at `from app.models.jobs import BackgroundJob`.

</domain>

<decisions>
## Implementation Decisions

### Sync Job + SyncJob Coexistence (INSTR-01)

- **D-01:** Sync runs write a `BackgroundJob` record IN ADDITION TO the existing `SyncJob` record (parallel write). `SyncJob` continues unchanged — nothing that reads it breaks. This applies to all four sync entry points: `run_daily_sync`, `run_full_resync`, `run_initial_sync`, `run_historical_sync`.
- **D-02:** `BackgroundJob.org_id` = `connection.organization_id`; `BackgroundJob.platform_connection_id` = `connection.id`. Both sourced from the existing `PlatformConnection` row that each sync function already fetches.
- **D-03:** `job_type` values: `"sync_daily"`, `"sync_full"`, `"sync_initial"`, `"sync_historical"` for the four sync entry points respectively.

### Progress Tracking

- **D-04:** Sync jobs use 0 → 1 progress (`progress_total = 1` on RUNNING, `progress_current = 1` on COMPLETE/FAILED). Sync does not expose an asset count before finishing.
- **D-05:** Download jobs track files downloaded / total queued (INSTR-02). `progress_total` = queue size at job start; `progress_current` increments after each successful or failed asset download. A single `BackgroundJob` is created per download batch invocation (`_run_google_ads_asset_downloads`, `_run_dv360_asset_downloads`, TikTok download equivalents).
- **D-06:** Autofill jobs: one `BackgroundJob` per `run_autofill_for_asset` invocation (one record per asset). `progress_total = 1`, `progress_current = 1` on completion. `job_type = "autofill"`. `org_id` = asset's `organization_id`.

### Scoring Job Scope (INSTR-04, INSTR-05)

- **D-07:** Scoring creates one `BackgroundJob` per scored asset (not one per batch). `job_type = "scoring"`. `org_id = asset.organization_id`. `platform_connection_id` = asset's connection if available, else `NULL`.
- **D-08:** Scoring `output` JSONB schema: `{"score": <float>, "endpoint_type": "<VIDEO|STATIC_IMAGE>", "brainsuite_job_id": "<str>", "dimensions": {<BrainSuite dimension map>}}`. Compact — no full API response blob.
- **D-09:** Scoring `metadata_` JSONB stores: `{"asset_id": "<uuid>", "creative_score_result_id": "<uuid>"}` for cross-reference to the existing `creative_score_results` table.

### Output JSONB Schemas

- **D-10:** Autofill `output` JSONB schema (INSTR-03): `{"fields": [{"name": "<field_name>", "value": "<determined_value>", "source": "<gemini|whisper>", "confidence": "<str|null>"}], "whisper_transcript": "<str|null>", "language": "<lang_code>"}`. No raw Gemini API response stored.
- **D-11:** Download `output` JSONB schema: `{"downloaded": [{"asset_id": "<uuid>", "url": "<minio_url>"}], "failed": [{"asset_id": "<uuid>", "error": "<str>"}]}`. Manifest for MON-04 drill-in.
- **D-12:** Sync `output` JSONB schema: `{"platform": "<meta|tiktok|google_ads|dv360>", "sync_job_id": "<SyncJob.id>", "records_fetched": <int>, "records_processed": <int>}`. Links to SyncJob for deeper detail.

### Error JSONB Schema (all job types)

- **D-13:** When a job fails, `error` JSONB = `{"type": "<ExceptionClassName>", "message": "<str>", "traceback": "<str truncated at 10000 chars>"}`. Satisfies MON-05 (10 KB traceback display). `status` = `"FAILED"`, `ended_at` = now.

### Session Isolation

- **D-14:** Follow the established session-per-operation pattern: open a fresh DB session to write each `BackgroundJob` status update, then close it before any external HTTP calls. Never hold a session open during BrainSuite API polling or platform API calls.
- **D-15:** Progress updates for download jobs (INSTR-02) use a fresh session per increment. Since download functions are already async and session-per-operation, this is a natural extension.

### Helper Abstraction

- **D-16:** Introduce a thin helper `create_background_job(job_type, org_id, platform_connection_id=None, metadata=None) -> UUID` and `update_background_job(job_id, status, progress_current=None, progress_total=None, output=None, error=None)` in a new file `backend/app/services/sync/job_tracker.py`. These handle session lifecycle internally. All four job types call these helpers — no duplication.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — INSTR-01 through INSTR-05 (full requirement text + acceptance criteria)
- `.planning/ROADMAP.md` §Phase 17 — Success criteria for this phase

### Schema
- `backend/app/models/jobs.py` — `BackgroundJob` model: all columns, types, indexes, FK constraints
- `backend/app/models/performance.py` §SyncJob — Existing `SyncJob` schema (preserve — parallel write only)

### Key Service Entry Points
- `backend/app/services/sync/scheduler.py` — `run_daily_sync` (L112), `run_full_resync` (L427), `run_initial_sync` (L707), `run_historical_sync` (L938); download helpers `_run_google_ads_asset_downloads` (L362), `_run_dv360_asset_downloads` (L399)
- `backend/app/services/sync/scoring_job.py` — `run_scoring_batch` (L44); per-asset scoring logic (L400–510)
- `backend/app/services/ai_autofill.py` — `run_autofill_for_asset` (L116)

### Session Pattern
- `backend/app/db/base.py` — `get_session_factory()` — session-per-operation pattern (D-14 constraint)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_session_factory()` — already used by all four service files for session-per-operation; new `job_tracker.py` follows the same pattern
- `SyncJob` write pattern in `scheduler.py` (L151–160) — template for parallel `BackgroundJob` write
- `brainsuite_job_id` on `CreativeScoreResult` (L484) — source for `output.brainsuite_job_id` in scoring jobs

### Established Patterns
- **Session-per-operation**: every DB write uses `async with get_session_factory()() as db:` then closes before any HTTP call — `BackgroundJob` updates must follow the same pattern (D-14)
- **`_supersede_running_jobs`** (L86): existing pattern for marking prior RUNNING jobs FAILED before starting a new run — inspect for sync job deduplication analogy
- **status strings**: PENDING, RUNNING, COMPLETE, FAILED — consistent with `SyncJob` and required by `BackgroundJob` (from Phase 16 decisions)
- **`asyncio.create_task`** for download fire-and-forget: download helpers are spawned as background tasks; `BackgroundJob` must be created BEFORE `create_task()` so the job ID is available for progress updates

### Integration Points
- `run_daily_sync` / `run_full_resync` / `run_initial_sync` / `run_historical_sync` — each creates `SyncJob` early in the function body; `BackgroundJob` write goes in the same location (after connection fetch, before sync dispatch)
- `run_scoring_batch` inner loop (L400–510) — per-asset scoring; `BackgroundJob` created per asset at loop start, updated on poll completion or failure
- `run_autofill_for_asset` — single asset; `BackgroundJob` created at function entry, updated on Gemini/Whisper completion or exception
- Download helpers — `BackgroundJob` created at function entry with `progress_total = len(asset_queue)`, incremented per download

</code_context>

<specifics>
## Specific Ideas

- The `job_tracker.py` helper pattern (D-16) keeps instrumentation DRY — `create_background_job` and `update_background_job` are thin wrappers, not a framework.
- Sync output links `sync_job_id` to the parallel `SyncJob` record so the monitoring UI can deep-link if needed.
- Download `output.downloaded` and `output.failed` manifests are built up incrementally and written on job completion (not per-file, to avoid excessive DB writes).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 17-service-instrumentation*
*Context gathered: 2026-05-08*
