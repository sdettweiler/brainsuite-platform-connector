# Phase 6: Historical Backfill + Score History Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 06-historical-backfill-score-history-schema
**Areas discussed:** Backfill scope, PG partitioning approach (dropped), History seeding strategy (dropped), Backfill execution model

---

## Backfill Scope

| Option | Description | Selected |
|--------|-------------|----------|
| UNSCORED only | Only queue assets with scoring_status=UNSCORED. FAILED stay FAILED. | ✓ |
| UNSCORED + FAILED | Also reset FAILED assets to UNSCORED for a retry. | |

**User's choice:** UNSCORED only

---

| Option | Description | Selected |
|--------|-------------|----------|
| All orgs, cross-tenant | Single admin call queues assets for every organization. | ✓ |
| Caller's org only | Scoped to current_user.organization_id. | |

**User's choice:** All orgs, cross-tenant

**Notes:** Backfill is treated as a one-time platform migration — not a per-tenant action.

---

## PG Partitioning + History Seeding — DROPPED

**Discussion outcome:** User clarified that BrainSuite scores are static — a creative is scored once and the score does not change over time. A trend chart would have at most one data point per asset. TREND-01 (history schema), TREND-02 (write after scoring), and TREND-03 (trend chart) were dropped from the v1.1 milestone entirely.

The PG partitioning and history seeding questions became moot and were not discussed further.

---

## Backfill Execution Model

| Option | Description | Selected |
|--------|-------------|----------|
| Call score_asset_now() per asset | Background task calls existing per-asset scoring function immediately for each UNSCORED asset. | ✓ |
| Reset to UNSCORED, let scheduler pick up | Assets already UNSCORED; scheduler picks them up in next 15-min tick. | |

**User's choice:** Call score_asset_now() per asset — process immediately, don't wait for scheduler cycles.

---

| Option | Description | Selected |
|--------|-------------|----------|
| 202 + count queued | Return assets_queued count immediately. | ✓ |
| 202 fire-and-forget | Just return 202 with no body. | |

**User's choice:** 202 + count queued

---

## Claude's Discretion

- Whether to mount the backfill endpoint under existing scoring router or a new `/admin` prefix
- Concurrency strategy inside background loop (sequential vs. asyncio.gather with semaphore)
- Per-asset error handling inside backfill loop

## Deferred Ideas

- Score history table and trend chart (TREND-01/02/03) — dropped from v1.1 entirely; scores are static
