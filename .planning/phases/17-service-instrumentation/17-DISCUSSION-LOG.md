# Phase 17: Service Instrumentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 17-service-instrumentation
**Areas discussed:** Sync + SyncJob coexistence, Progress definition per type, Scoring batch org scope, Output JSONB verbosity

---

## Sync + SyncJob Coexistence

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel write | Sync continues writing SyncJob as today. Also writes a BackgroundJob with the same lifecycle. Both tables stay live. | ✓ |
| Migrate sync to BackgroundJob only | Sync stops writing SyncJob. All job tracking goes through BackgroundJob. | |
| BackgroundJob for new flows only | SyncJob stays as the single source for sync. Only download, autofill, scoring write BackgroundJob. INSTR-01 re-scoped. | |

**User's choice:** Parallel write
**Notes:** All four sync entry points instrumented (run_daily_sync, run_full_resync, run_initial_sync, run_historical_sync). org_id sourced from connection.organization_id.

---

## Progress Definition Per Type

| Question | Options | Selected |
|----------|---------|----------|
| Sync progress | 0→1 (started/done) / Assets fetched/total / You decide | 0→1 |
| Download progress | Files downloaded/total (INSTR-02) / 0→1 only | Files downloaded/total |
| Autofill scope | One BackgroundJob per asset / One per sync run / You decide | One per asset |

**User's choice:** Sync = 0→1; Download = granular per-file; Autofill = one job per run_autofill_for_asset call.
**Notes:** Autofill is per-asset by design (run_autofill_for_asset fires once per asset from create_task).

---

## Scoring Batch Org Scope

| Option | Description | Selected |
|--------|-------------|----------|
| One BackgroundJob per org in batch | Group assets by org; one job per org. | |
| One system BackgroundJob + nullable org_id | One job for whole batch, schema migration required. | |
| One BackgroundJob per scored asset | Finest granularity. org_id = asset.organization_id. | ✓ |

**User's choice:** One BackgroundJob per scored asset.
**Notes:** Output schema: {score, endpoint_type, brainsuite_job_id, dimensions}. metadata_ stores {asset_id, creative_score_result_id} for cross-reference.

---

## Output JSONB Verbosity

| Question | Options | Selected |
|----------|---------|----------|
| Autofill output | Structured summary only / Full Gemini JSON + fields / Fields + raw trimmed at 10KB | Structured summary only |
| Error JSONB | Exception type + message + traceback (10KB cap) / Message only / You decide | Exception type + message + traceback |

**User's choice:** Structured summary for autofill output (no raw Gemini response). Error JSONB includes type, message, and traceback truncated at 10,000 chars.
**Notes:** Satisfies INSTR-03 (field names + values + source) and MON-05 (10KB traceback display) without storing large API blobs.

---

## Claude's Discretion

- `job_tracker.py` helper design (D-16): thin `create_background_job` / `update_background_job` helpers — implementation details left to planner
- Exact session isolation points within each function left to planner (constrained by D-14 session-per-operation rule)
- Download manifest accumulation strategy (build in memory, write once on completion) left to planner

## Deferred Ideas

None — discussion stayed within phase scope.
