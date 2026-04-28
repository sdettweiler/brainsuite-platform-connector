---
phase: 11-per-org-config-schema-pipeline-wiring
fixed_at: 2026-04-16T13:21:27Z
review_path: .planning/phases/11-per-org-config-schema-pipeline-wiring/11-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 11: Code Review Fix Report

**Fixed at:** 2026-04-16T13:21:27Z
**Source review:** .planning/phases/11-per-org-config-schema-pipeline-wiring/11-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Seed migration assigns phantom `bvl_field_id` on re-run

**Files modified:** `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py`
**Commit:** fda5bb5
**Applied fix:** Changed `ON CONFLICT DO NOTHING` (no target) to `ON CONFLICT (organization_id, name) DO NOTHING` for the explicit conflict target. Replaced the `bvl_field_id = field_id` assignment with a follow-up `SELECT id FROM metadata_fields WHERE organization_id = :org_id AND name = 'brainsuite_brand_values_language'` query that fetches the actual persisted row id after the INSERT — on first run this returns the row just inserted, on re-run it returns the pre-existing row. This ensures `metadata_field_values` rows always reference a real `field_id` rather than a phantom UUID that was never persisted.

### CR-02: `poll_job_status` 401 branch burns all poll attempts in a tight loop

**Files modified:** `backend/app/services/brainsuite_score.py`, `backend/app/services/brainsuite_static_score.py`
**Commit:** 738ab8d
**Applied fix:** Added `consecutive_401s = 0` counter before the poll loop in both `BrainSuiteScoreService.poll_job_status` and `BrainSuiteStaticScoreService.poll_job_status`. On a 401 response the counter increments, `_invalidate_token` is called, and `asyncio.sleep(poll_interval)` is awaited before `continue` — so a 401 retry now waits the same interval as any other poll. If `consecutive_401s >= 3` the loop raises `BrainSuiteJobError` with a clear message naming the credential problem rather than silently timing out. Added `consecutive_401s = 0` reset on any non-401 response to allow recovery if a single stale token causes a transient 401.

### WR-01: Detached ORM objects accessed outside session in `score_asset_now` and `run_scoring_batch`

**Files modified:** `backend/app/services/sync/scoring_job.py`
**Commit:** 166d267
**Applied fix:** In `score_asset_now`, added `db.expunge_all()` inside the `async with` block immediately after `result.one_or_none()` returns a row — while the session is still open and all column values are loaded. In `run_scoring_batch`, added `db.expunge_all()` immediately after `await db.commit()` inside the Phase 1 session block, before the `async with` context exits. Both calls detach the ORM objects with their loaded state intact, preventing `DetachedInstanceError` when `asset.organization_id`, `asset.platform`, `asset.asset_url`, etc. are accessed in Phase 2 / Phase 3.5.

### WR-02: `datetime.utcnow` used as column default on `timezone=True` columns

**Files modified:** `backend/app/models/brainsuite_config.py`, `backend/app/api/v1/endpoints/auth.py`
**Commit:** b923cd6
**Applied fix:** In `brainsuite_config.py`: added `timezone` to the `datetime` import; replaced all four `default=datetime.utcnow` / `onupdate=datetime.utcnow` references (two in `OrgBrainsuiteConfig`, two in `OrgBrainsuiteFieldMapping`) with `default=lambda: datetime.now(timezone.utc)` / `onupdate=lambda: datetime.now(timezone.utc)`. In `auth.py`: added `timezone` to the top-level `from datetime import datetime, timedelta, timezone` import; replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` in the `login` handler (last_login assignment and RefreshToken expires_at) and in the `refresh_token` handler (new RefreshToken expires_at); removed the redundant inline `from datetime import timezone` that was previously needed inside `refresh_token`.

### WR-03: 2FA TOTP code presence checked but value never validated

**Files modified:** `backend/app/api/v1/endpoints/auth.py`
**Commit:** 37e1bd1
**Applied fix:** Added TOTP verification after the presence check in the `login` handler. Uses `pyotp.TOTP(user.two_factor_secret).verify(payload.totp_code)` (note: the model column is `two_factor_secret`, not `totp_secret` as the review named it — confirmed by reading `backend/app/models/user.py`). Raises `HTTPException(status_code=401, detail="Invalid 2FA code")` if verification fails. `pyotp==2.9.0` is already present in `backend/requirements.txt`.

### WR-04: `score_row.creative_asset_id` accessed on detached instance after session closes

**Files modified:** `backend/app/services/sync/scoring_job.py`
**Commit:** 166d267
**Applied fix:** Resolved by the same `db.expunge_all()` fix applied for WR-01 in `score_asset_now`. The expunge call keeps all loaded column values (including `creative_asset_id`) accessible on the detached instances after the session context exits. Committed in the same atomic commit as WR-01.

---

_Fixed: 2026-04-16T13:21:27Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
