# Phase 9: AI Metadata Auto-Fill - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Pipeline-integrated AI metadata auto-fill. Each `MetadataField` has an `auto_fill_enabled` flag configurable on the metadata config page. When scoring runs, enabled fields are inferred via OpenAI (GPT-4o Vision + Whisper) and written directly to asset metadata — no user confirmation step. Account-level defaults propagate to asset values and serve as fallback if inference fails. Users can overwrite values manually; doing so resets the asset to `UNSCORED` (no immediate rescore — the scheduler picks it up).

**This is NOT a dialog button.** The original AI-04 requirement (Auto-fill button in asset detail dialog) is superseded by the pipeline-integration design.

</domain>

<decisions>
## Implementation Decisions

### Auto-fill Configuration

- **D-01:** `MetadataField` model gets an `auto_fill_enabled` boolean column (default `false`). Org admins toggle it per-field on the Configuration > Metadata page. No schema changes to per-asset value storage — auto-fill writes directly to `AssetMetadataValue`.
- **D-02:** Auto-fill runs as part of the existing scoring job (`run_scoring_batch()` in `scoring_job.py`), not a separate scheduler or on-demand endpoint. Triggered whenever an asset is scored (batch or immediate rescore).
- **D-03:** Account-level `default_value` (on `MetadataField`) is propagated to `AssetMetadataValue` at scoring time if no value exists yet. Auto-fill may then overwrite the default. `default_value` is the fallback if inference fails.
- **D-04:** Auto-fill results are written directly to `AssetMetadataValue` — no intermediate suggestions table for user review and no confirmation step.

### Field Behavior

- **D-05:** AI-inferred fields (via OpenAI) when `auto_fill_enabled = true`:
  - **Language** — GPT-4o Vision: detect the primary language of the creative content (language only, not market/region)
  - **Brand Names** — GPT-4o Vision: extract brand names visible or audible in the creative
  - **Voice Over transcript** — Whisper API: full transcript of voice-over audio (not a yes/no boolean — store the full text)
  - **Voice Over Language** — Whisper API: language of the voice-over audio
- **D-06:** Deterministic fields populated from sync data (no AI, always populate):
  - **Project Name** → campaign name from ad sync data
  - **Asset Name** → ad name from ad sync data
- **D-07:** Fixed field (no AI, no sync):
  - **Asset Stage** → always hardcoded to `"Final"` regardless of creative content

### AI Provider

- **D-08:** OpenAI is the default and only AI provider for all auto-detection:
  - Image/video frame analysis (Language, Brand Names): GPT-4o Vision (or GPT-4o-mini for cost)
  - Audio transcription (VO transcript, VO Language): Whisper API (`whisper-1`)
- **D-09:** `OPENAI_API_KEY` is optional. If not configured, all AI-inferred fields (D-05) degrade gracefully — fall back to `default_value` or leave the field unset. No hard error. Deterministic fields (D-06) and fixed fields (D-07) are unaffected.

### State Machine

- **D-10:** `ai_metadata_suggestions` table renamed in concept to an **execution tracking table** — one row per asset, used to track inference status. Schema: `(id, asset_id, org_id, ai_inference_status, created_at, updated_at)`. Status: `PENDING | COMPLETE | FAILED`.
- **D-11:** No confidence tracking at any level — skip entirely. If a value is returned by OpenAI, it is written. If not, fallback applies.
- **D-12:** `FAILED` status is **retried** on the next scoring run (status reset to `PENDING` when the scoring job picks up the asset again). Retry is automatic — no manual trigger needed.

### User Overrides & Rescoring

- **D-13:** Users can manually overwrite any auto-filled `AssetMetadataValue` from the asset detail dialog.
- **D-14:** A manual metadata value edit resets the asset's `scoring_status` to `UNSCORED`. It does NOT immediately trigger scoring — the 15-minute APScheduler batch picks it up. This prevents multiple rescores when a user edits several fields in sequence.

### Claude's Discretion

- GPT-4o vs GPT-4o-mini for vision: researcher/planner should evaluate cost vs quality for brand name extraction on typical ad creative. Either is acceptable.
- Whether VO transcript is stored as a full text field or truncated (e.g. 2000-char limit) — planner decides based on `MetadataField` field_type constraints.
- Exact field name mappings (which `MetadataField.name` values correspond to Language, Brand Names, VO transcript, VO Language, etc.) — researcher should check existing `MetadataField` seed data or configuration conventions.
- Image/video frame extraction approach for GPT-4o Vision — researcher should confirm best practice for video frames (extract first frame? multiple? thumbnail?).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Metadata model & API
- `backend/app/models/metadata.py` — `MetadataField`, `MetadataFieldValue`, `AssetMetadataValue` models; `auto_fill_enabled` column will be added here
- `backend/app/api/v1/endpoints/assets.py` — existing metadata CRUD endpoints (`PATCH /{asset_id}/metadata`, `GET /metadata/fields`, etc.); Alembic migration pattern to follow

### Scoring pipeline — integration point
- `backend/app/services/sync/scoring_job.py` — `run_scoring_batch()` — auto-fill hook goes inside this function, after scoring completes
- `backend/app/api/v1/endpoints/scoring.py` — `rescore_asset()` — immediate rescore path; same auto-fill hook must also run here

### Creative model — sync data for deterministic fields
- `backend/app/models/creative.py` — check for `campaign_name` and `ad_name` columns (source for Project Name and Asset Name deterministic fill)

### Frontend — metadata config page
- `frontend/src/app/features/configuration/pages/metadata.component.ts` — metadata config page; `auto_fill_enabled` toggle must be added here per-field

### Asset detail dialog — metadata display and editing
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` — shows `metadata_values`; manual edit triggers rescoring reset (D-14)

### Phase requirements
- `.planning/REQUIREMENTS.md` §AI-01, §AI-02, §AI-03, §AI-05, §AI-06 — note: AI-04 (dialog button) is superseded by pipeline-integration design in D-02

### Prior phase patterns
- `.planning/phases/08-score-to-roas-correlation/08-CONTEXT.md` — BackgroundTasks + 202 pattern; rescore state machine pattern
- `.planning/phases/05-brainsuite-image-scoring/05-CONTEXT.md` — `ScoringEndpointType` enum, scoring_job branch pattern, Alembic migration patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_scoring_batch()` in `scoring_job.py` — auto-fill runs inside this function; same session-per-operation pattern applies
- `BackgroundTasks` + 202 response pattern from `scoring.py` rescore endpoint — reuse if any on-demand path is needed
- `PATCH /assets/{asset_id}/metadata` in `assets.py` — existing write path for `AssetMetadataValue`; auto-fill should use the same write logic
- `MetadataField.default_value` column already exists — serves as fallback per D-03

### Established Patterns
- Session-per-operation: never hold DB session during external HTTP calls (OpenAI/Whisper)
- `on_conflict_do_nothing` for status tracking inserts (prevents re-sync resetting completed state)
- String columns with UPPERCASE values for status fields (e.g. `PENDING`, `COMPLETE`, `FAILED`)
- Alembic migrations for all schema changes

### Integration Points
- `run_scoring_batch()` → add auto-fill after `COMPLETE` scoring result written
- `MetadataField` → add `auto_fill_enabled` boolean column via Alembic migration
- `metadata.component.ts` → add `auto_fill_enabled` toggle per field in the config UI
- MinIO presigned URL → asset must be fetched server-side before passing to OpenAI (same pattern as BrainSuite image scoring in Phase 5)

</code_context>

<specifics>
## Specific Ideas

- **VO is a transcript, not boolean**: Voice Over field should store the full transcript text returned by Whisper, not a yes/no value. If Whisper returns empty/no speech, the field gets the `default_value` fallback.
- **Language ≠ Market**: The language inference detects the content language only (e.g. "English", "German"). Market/region targeting is not inferred — do not combine with country codes unless the existing `MetadataField` label explicitly calls for it.
- **Asset Stage hardcoded**: Asset Stage is always "Final" — no inference, no sync data, just a constant. This simplifies the pipeline; no AI call needed for this field.
- **Rescore on edit**: When a user edits a metadata value in the asset detail dialog, the backend should set `scoring_status = "UNSCORED"` on the asset's `CreativeScoreResult` row. The 15-minute batch will pick it up. No immediate API call to BrainSuite.

</specifics>

<deferred>
## Deferred Ideas

- Per-tenant daily OpenAI spend cap — listed as future requirement AI-v2-01 in REQUIREMENTS.md; not in scope for Phase 9
- Per-field confidence tracking — discussed and explicitly deferred; may be revisited if accuracy issues emerge in production
- On-demand "Re-run auto-fill" button in asset detail dialog — auto-fill is pipeline-integrated for v1.1; manual trigger is a potential v1.2 enhancement
- AI-04 (original requirement): Asset detail dialog Auto-fill button with confidence indicators and user review — superseded by pipeline-integration design. If per-asset on-demand inference is needed later, it can be layered on top.

</deferred>

---

*Phase: 09-ai-metadata-auto-fill*
*Context gathered: 2026-04-01*
