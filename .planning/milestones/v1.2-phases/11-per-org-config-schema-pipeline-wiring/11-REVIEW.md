---
phase: 11-per-org-config-schema-pipeline-wiring
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py
  - backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py
  - backend/app/api/v1/endpoints/auth.py
  - backend/app/models/__init__.py
  - backend/app/models/brainsuite_config.py
  - backend/app/services/brainsuite_score.py
  - backend/app/services/brainsuite_static_score.py
  - backend/app/services/sync/scoring_job.py
  - backend/tests/test_phase11_pipeline.py
  - backend/tests/test_phase11_schema.py
  - backend/tests/test_phase11_seed.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

This phase introduces per-org BrainSuite configuration (credentials + app names stored in `org_brainsuite_config`), a field-mapping table, two brand-values metadata fields seeded via migration and `auth.py` registration, and a full pipeline re-wire so that both video and static scoring services use per-org credentials from the database rather than global settings.

The overall design is sound — the model schema, FK cascade, unique constraint, and service refactor are all correct. Two critical issues were found: a seed migration idempotency bug that will corrupt data on re-run, and a tight 401 polling loop in both score services that consumes all poll attempts with no sleep. Four warnings cover detached-instance access on ORM objects across session boundaries, naive datetimes mixed with timezone-aware columns, a missing 2FA TOTP validation in auth (pre-existing but in scope), and a minor scope error in `score_asset_now` accessing a detached `creative_asset_id` attribute.

---

## Critical Issues

### CR-01: Seed migration assigns phantom `bvl_field_id` on re-run, inserting orphan `metadata_field_values` rows

**File:** `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py:73-113`

**Issue:** The migration generates a fresh UUID (`field_id = str(uuid.uuid4())`) on every iteration and then assigns `bvl_field_id = field_id` when the field name is `brainsuite_brand_values_language` (line 94). When `ON CONFLICT DO NOTHING` fires (re-run), the INSERT is a no-op — the row in `metadata_fields` retains its original UUID — but `bvl_field_id` is set to the newly-generated UUID that was never persisted. The code then inserts 31 `metadata_field_values` rows referencing this phantom `field_id`. If `metadata_field_values.field_id` has a FK constraint these inserts fail with a constraint error; if the FK is deferred or missing they silently create orphan rows. Either outcome is a correctness failure.

**Fix:** Query the actual inserted (or pre-existing) `id` after the INSERT:

```python
for name, label, ftype, required, default, sort in fields_def:
    field_id = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO metadata_fields
            (id, organization_id, name, label, field_type, is_required, default_value, is_active, sort_order, created_at, updated_at)
        VALUES
            (:id, :org_id, :name, :label, :ftype, :required, :default_val, true, :sort, :now, :now)
        ON CONFLICT (organization_id, name) DO NOTHING
    """), {...})

    if name == "brainsuite_brand_values_language":
        # Fetch the actual persisted id (handles both first-run and re-run)
        row = conn.execute(sa.text("""
            SELECT id FROM metadata_fields
            WHERE organization_id = :org_id AND name = 'brainsuite_brand_values_language'
        """), {"org_id": org_id}).fetchone()
        bvl_field_id = str(row[0]) if row else None
```

Note also that `ON CONFLICT DO NOTHING` without a conflict target (current line 80) relies on PostgreSQL inferring the constraint from the row. Adding an explicit conflict target `ON CONFLICT (organization_id, name) DO NOTHING` is clearer and requires a unique constraint on `(organization_id, name)` — verify this constraint exists on `metadata_fields`.

---

### CR-02: `poll_job_status` 401 branch does not sleep — burns all poll attempts in a tight loop

**File:** `backend/app/services/brainsuite_score.py:360-362`
**Also:** `backend/app/services/brainsuite_static_score.py:418-420`

**Issue:** When the GET poll response is HTTP 401, the code invalidates the cached token and calls `continue` without sleeping. On the next loop iteration `_get_token` fetches a fresh token (network round-trip), but if the credentials are wrong or the token endpoint returns a short-lived or invalid token, every subsequent GET poll will also return 401. With `max_polls=60` and no sleep the function can exhaust all 60 attempts in seconds, treating a transient auth failure as a timeout and raising `BrainSuiteJobError("polling timed out")` — masking the real 401 cause.

**Fix:** Apply the same `poll_interval` sleep after a 401, and add a per-poll 401 counter to abort early with a clear error if auth is persistently broken:

```python
consecutive_401s = 0
for poll_num in range(max_polls):
    token = await self._get_token(org_id, client_id, client_secret)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    if resp.status_code == 401:
        consecutive_401s += 1
        self._invalidate_token(org_id)
        if consecutive_401s >= 3:
            raise BrainSuiteJobError(
                f"BrainSuite job {job_id}: persistent 401 — check org credentials"
            )
        await asyncio.sleep(poll_interval)
        continue

    consecutive_401s = 0
    resp.raise_for_status()
    ...
```

Apply the identical fix to `BrainSuiteStaticScoreService.poll_job_status`.

---

## Warnings

### WR-01: Detached ORM objects accessed outside session in `score_asset_now` and `run_scoring_batch`

**File:** `backend/app/services/sync/scoring_job.py:126-164` (score_asset_now), `61-95` (run_scoring_batch)

**Issue:** In `score_asset_now`, `row = result.one_or_none()` is obtained inside the `async with` block (line 132) but `score_row` and `asset` are unpacked and accessed *after* the session closes (lines 138-164). With SQLAlchemy's default `expire_on_commit=True`, ORM objects are expired when the session closes; accessing any attribute on a detached expired instance raises `DetachedInstanceError`. Attributes accessed on `asset` outside the session include `asset.organization_id`, `asset.platform`, `asset.placement`, `asset.asset_url`, `asset.ad_name` — all inside `_process_asset`. The same pattern affects `run_scoring_batch` where `asset_row` objects are stored in `batch[]` and passed to `_process_asset` after the Phase 1 session closes.

**Fix (option A — preferred):** Call `db.expunge_all()` before the session closes to detach objects while keeping their loaded state:

```python
async with get_session_factory()() as db:
    result = await db.execute(
        select(CreativeScoreResult, CreativeAsset)
        .join(CreativeAsset, CreativeAsset.id == CreativeScoreResult.creative_asset_id)
        .where(CreativeScoreResult.id == score_id)
    )
    row = result.one_or_none()
    if row:
        db.expunge_all()  # detach while attributes are still loaded

score_row, asset = row
```

**Fix (option B):** Use `make_transient()` from `sqlalchemy.orm` on each object, or convert to plain dataclasses/dicts before the session closes.

---

### WR-02: `datetime.utcnow` used as SQLAlchemy column default on `timezone=True` columns

**File:** `backend/app/models/brainsuite_config.py:31-34`

**Issue:** Both `created_at` and `updated_at` in `OrgBrainsuiteConfig` and `OrgBrainsuiteFieldMapping` declare `DateTime(timezone=True)` but use `default=datetime.utcnow` and `onupdate=datetime.utcnow`. `datetime.utcnow()` returns a naive datetime (no `tzinfo`). When SQLAlchemy writes a naive datetime to a `TIMESTAMPTZ` column, PostgreSQL interprets it as local server time, which is correct on UTC servers but will break on non-UTC deployments. Additionally, `datetime.utcnow` is deprecated in Python 3.12+.

**Fix:** Use `datetime.now(timezone.utc)` throughout:

```python
from datetime import datetime, timezone

created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
)
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
)
```

The same pattern applies to `auth.py` lines 234 and 244 (`user.last_login = datetime.utcnow()`, `expires_at=datetime.utcnow() + ...`).

---

### WR-03: 2FA TOTP code presence is checked but value is never validated

**File:** `backend/app/api/v1/endpoints/auth.py:230-232`

**Issue:** The login handler checks that a TOTP code is *present* when 2FA is enabled, but never validates the code against the user's TOTP secret:

```python
if user.is_two_factor_enabled:
    if not payload.totp_code:
        raise HTTPException(status_code=400, detail="2FA code required")
    # <-- no validation: any non-empty string passes
```

An attacker who knows a valid username/password can bypass 2FA by sending any arbitrary string as `totp_code`.

**Fix:** Validate the TOTP code against the stored secret before proceeding:

```python
import pyotp

if user.is_two_factor_enabled:
    if not payload.totp_code:
        raise HTTPException(status_code=400, detail="2FA code required")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(payload.totp_code):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
```

---

### WR-04: `score_asset_now` accesses `score_row.creative_asset_id` on a detached instance after the UNSUPPORTED early-return check

**File:** `backend/app/services/sync/scoring_job.py:141-146`

**Issue:** At line 144, `score_row.creative_asset_id` is accessed in the log message inside the `UNSUPPORTED` branch. `score_row` is already detached at this point (session closed at line 133). While `endpoint_type` is the first attribute read (line 139) and may succeed if it was loaded into the result row, `creative_asset_id` is a separate column that may not have been eagerly fetched into the result set depending on the select projection and SQLAlchemy column loading strategy, triggering `DetachedInstanceError`.

**Fix:** Extract all needed scalar values before the session closes, or apply the `expunge_all()` fix from WR-01:

```python
async with get_session_factory()() as db:
    result = await db.execute(...)
    row = result.one_or_none()
    if row:
        db.expunge_all()

if not row:
    ...
    return

score_row, asset = row
endpoint_type = score_row.endpoint_type
asset_id_for_log = score_row.creative_asset_id  # safe: loaded in same query
```

---

## Info

### IN-01: `org_brainsuite_config` migration missing `server_default` for `created_at` / `updated_at`

**File:** `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py:31-32`

**Issue:** The `created_at` and `updated_at` columns are declared `nullable=False` but have no `server_default`. If a row is ever inserted via raw SQL (not the ORM, which fills in the Python-side default), the insert will fail with a NOT NULL constraint violation. The ORM model handles this via `default=datetime.utcnow`, but migrations and data-load scripts bypass the ORM layer.

**Fix:** Add `server_default=sa.text("NOW()")` to both timestamp columns in the migration:

```python
sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
```

Apply the same to the `org_brainsuite_field_mappings` table (lines 60-61).

---

### IN-02: `build_scoring_payload` falls back to hardcoded placeholder strings for required briefing fields

**File:** `backend/app/services/brainsuite_score.py:488-490`

**Issue:** `projectName` falls back to `"Spring Campaign 2026"` and `assetName` falls back to `"asset_name"` when the corresponding metadata keys are absent. The project name fallback is time-specific and will be semantically wrong after 2026. Both are low-signal placeholder values that may affect BrainSuite scoring results silently — there is no log warning when a fallback is used.

**Fix:** At minimum, log a warning when a fallback fires, and consider changing the project name fallback to a generic value like `"Default Campaign"`:

```python
project_name = metadata.get("brainsuite_project_name")
if not project_name:
    logger.warning("Scoring asset %s: brainsuite_project_name not set, using fallback", asset_name)
    project_name = "Default Campaign"

asset_name_meta = metadata.get("brainsuite_asset_name")
if not asset_name_meta:
    logger.warning("Scoring asset %s: brainsuite_asset_name not set, using filename", asset_name)
    asset_name_meta = asset_name
```

---

_Reviewed: 2026-04-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
