---
phase: 15-tiktok-asset-download
plan: "02"
subsystem: testing
tags:
  - tiktok
  - scoring
  - gate
  - unit-tests
  - pytest

dependency_graph:
  requires:
    - phase: "15-01"
      provides: "TikTokSyncService download methods + _enrich_from_ad_get extension populating asset_url"
    - "backend/app/services/sync/scoring_job.py (SystemConfig.scoring_enabled gate at line 66)"
    - "backend/app/services/scoring_endpoint_type.py (get_endpoint_type lookup table)"
    - "backend/app/services/sync/harmonizer.py (line 372: raw.creative_url or raw.asset_url pipe)"
  provides:
    - "test_scoring_gate.py — 10 unit tests: scoring gate toggle, cross-platform endpoint types, TikTok harmonizer asset_url pipe"
    - "D-05 acceptance evidence: test_all_platforms_honor_scoring_enabled confirms all 4 platforms' VIDEO assets reach non-UNSUPPORTED endpoint type"
  affects:
    - "Phase 16+ — Phase 15 fully verified; TikTok asset download + scoring gate both confirmed working"

tech_stack:
  added: []
  patterns:
    - "Scoring gate mocked via single mock_db with side_effect list across both DB sessions"
    - "AsyncMock context manager pattern: mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)"

key_files:
  created:
    - path: backend/tests/test_scoring_gate.py
      description: "10 unit tests: scoring gate toggle (3), endpoint type correctness (4), harmonizer asset_url pipe (3)"
  modified: []

key_decisions:
  - "D-05 verified: scoring_enabled gate at scoring_job.py:66 is a single global control covering all 4 platforms — no platform-specific logic needed"
  - "TikTok IMAGE -> UNSUPPORTED by design (D-11): AI autofill reads asset_url directly, not via scoring queue"
  - "Harmonizer expression raw.creative_url or raw.asset_url correctly picks up Phase 15 asset_url when creative_url is None"

patterns_established:
  - "Scoring gate test pattern: patch get_session_factory, set execute.side_effect=[gate_result, batch_result], assert call_count"

requirements_completed:
  - TKTOK-01
  - TKTOK-02

duration: 8min
completed: "2026-05-08"
---

# Phase 15 Plan 02: TikTok Asset Download — Scoring Gate Verification Summary

**10 unit tests verifying the SystemConfig.scoring_enabled gate covers all 4 platforms and that TikTok VIDEO assets flow through the harmonizer into UNSCORED state via the raw.creative_url or raw.asset_url expression at harmonizer.py:372.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-08T16:26:00Z
- **Completed:** 2026-05-08T16:34:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Wrote `test_scoring_gate.py` with 10 tests across three groups: gate toggle, endpoint type correctness, harmonizer pipe
- Confirmed the D-05 acceptance criteria: `test_all_platforms_honor_scoring_enabled` proves META, TIKTOK, GOOGLE_ADS, DV360 VIDEO assets all map to a non-UNSUPPORTED endpoint type
- Confirmed `test_scoring_disabled_exits_early` produces exactly 1 db.execute call (SystemConfig select only — no batch query fired)
- Confirmed TikTok IMAGE -> UNSUPPORTED (by design, D-11): images not scored by BrainSuite, but AI autofill still operates on asset_url directly
- All 10 tests green; no regressions in pre-existing suite (pre-existing failures documented in Plan 01 SUMMARY are unrelated)

## Task Commits

1. **Task 1: Write cross-platform scoring gate tests and TikTok harmonizer pipe verification** - `42ff946` (test)

## Files Created/Modified

- `backend/tests/test_scoring_gate.py` — 10 unit tests covering scoring gate toggle (3 tests), endpoint type correctness for all 4 platforms (4 tests), and harmonizer raw.creative_url or raw.asset_url expression (3 tests)

## Decisions Made

None — plan executed exactly as specified. Tests were written precisely as provided in the plan's `<action>` block. No implementation deviations.

## Deviations from Plan

None — plan executed exactly as written. The test file content matches the plan specification exactly. All 10 tests pass.

## Issues Encountered

**Worktree path-safety:** Initial Write tool call used the main repo path instead of the worktree path (standard worktree hazard, per #3099). Detected via `git status` showing clean worktree. Corrected by copying the file to the worktree path and removing it from the main repo before staging. No data loss — the test file was identical.

## Known Stubs

None — this plan creates test-only files. No production code stubs.

## Threat Flags

No new threat surface. This plan adds test files only — no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check

Files created/modified:
- `backend/tests/test_scoring_gate.py` — exists in worktree (committed `42ff946`)

Commits verified:
- `42ff946`: test(15-02) — 10 tests

Acceptance criteria:
- `grep -c "def test_"` returns 10 — PASS
- `test_all_platforms_honor_scoring_enabled` present — PASS
- `test_tiktok_harmonizer_uses_asset_url_when_creative_url_is_none` present — PASS
- All 10 tests passed in Docker container — PASS
- All Phase 15 tests (21 total) passed together — PASS
- Pre-existing suite failures are pre-existing (documented in Plan 01 SUMMARY) — PASS

## Self-Check: PASSED

## Next Phase Readiness

- Phase 15 fully complete: Plan 01 (implementation) + Plan 02 (verification) both committed
- TikTok asset download gap closed: video and image assets flow to asset_url → harmonizer → UNSCORED → scoring queue
- scoring_enabled gate confirmed as single global control covering all 4 platforms
- Ready for Phase 16: Job Persistence Schema (background_jobs table)

---
*Phase: 15-tiktok-asset-download*
*Completed: 2026-05-08*
