---
phase: 14-youtube-cookies-admin-ui
plan: "01"
subsystem: backend-data-auth
tags: [system-config, superadmin, jwt, alembic, migration, singleton]
dependency_graph:
  requires: []
  provides: [SystemConfig model, get_current_superadmin dependency, JWT is_superuser claim, UserResponse.is_superuser]
  affects: [backend/app/api/v1/deps.py, backend/app/schemas/user.py, backend/app/api/v1/endpoints/auth.py]
tech_stack:
  added: []
  patterns: [singleton-guard pattern for DB-enforced single row, Fernet encryption placeholder for cookie columns]
key_files:
  created:
    - backend/app/models/system_config.py
    - backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py
  modified:
    - backend/app/api/v1/deps.py
    - backend/app/api/v1/endpoints/auth.py
    - backend/app/schemas/user.py
decisions:
  - "Used Text (not String(1000)) for cookie columns since YouTube cookies are multi-KB strings (D-06)"
  - "get_current_superadmin has no DB query — checks is_superuser directly from User model loaded by get_current_user"
  - "Migration downgrade intentionally does NOT reset is_superuser to avoid accidental privilege removal"
  - "is_superuser added to both access_token and refresh_token for consistent JWT claims"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 14 Plan 01: SystemConfig + SuperAdmin Foundation Summary

**One-liner:** SystemConfig singleton table with encrypted YouTube cookie columns, get_current_superadmin FastAPI dependency, and JWT/UserResponse is_superuser extension wired end-to-end.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | SystemConfig model + Alembic migration with SuperAdmin seed | faed672 | backend/app/models/system_config.py, backend/alembic/versions/x6y7z8a9b0c_... |
| 2 | SuperAdmin dependency + JWT claims extension + UserResponse schema | 54fd0f6 | backend/app/api/v1/deps.py, backend/app/api/v1/endpoints/auth.py, backend/app/schemas/user.py |

## What Was Built

### SystemConfig Model (backend/app/models/system_config.py)
- SQLAlchemy model for platform-wide singleton configuration table
- `singleton_guard: String(1)` with `unique=True` enforces exactly one row
- `youtube_cookies_encrypted: Text` and `youtube_cookies_backup_encrypted: Text` for Fernet-encrypted cookie storage
- `uq_system_config_singleton` UNIQUE constraint at DB level (T-14-02 mitigation)

### Alembic Migration (x6y7z8a9b0c)
- Chains from `w4x5y6z7a8b9` (Phase 13 last migration)
- Creates `system_config` table with all columns and singleton constraint
- Inserts default singleton row (`singleton_guard='X'`)
- Seeds `s.dettweiler@brainsuite.ai` as `is_superuser=true`
- Downgrade drops table only; does not reset `is_superuser`

### get_current_superadmin Dependency (backend/app/api/v1/deps.py)
- Added after `get_current_admin` function
- Checks `current_user.is_superuser` directly — no extra DB query
- Raises HTTP 403 with `detail="SuperAdmin privileges required"` for non-SuperAdmin users
- Does not take `db: AsyncSession` parameter (intentionally lighter than `get_current_admin`)

### JWT Claims Extension (backend/app/api/v1/endpoints/auth.py)
- `create_access_token` and `create_refresh_token` calls in login endpoint now include `"is_superuser": user.is_superuser`
- Enables Angular frontend to gate Admin menu without an extra API call

### UserResponse Schema Extension (backend/app/schemas/user.py)
- Added `is_superuser: bool = False` to `UserResponse` class
- `from_attributes = True` reads the field from SQLAlchemy User model automatically
- `/users/me` endpoint returns `is_superuser` with no additional endpoint changes needed

## Decisions Made

1. **Text vs String for cookie columns:** Used `Text` (not `String(1000)`) because YouTube cookies are multi-KB strings and would overflow 1000-char limit.
2. **No DB query in get_current_superadmin:** The `is_superuser` flag is already on the User model loaded by `get_current_user` from the JWT `sub` claim. A second DB query would be redundant.
3. **Downgrade does not reset is_superuser:** Removing SuperAdmin privileges on schema downgrade could lock out the admin account accidentally. This is an intentional safety choice.
4. **is_superuser in both access and refresh tokens:** Consistent JWT payload across token types avoids confusion if either is decoded independently.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UUID column type in Alembic migration**
- **Found during:** Task 1
- **Issue:** Plan scaffold used `sa.dialects.postgresql.UUID(as_uuid=True)` which requires an extra import. Project convention (seen in initial migration) uses `sa.UUID()` directly.
- **Fix:** Changed to `sa.UUID()` to match existing codebase migration pattern.
- **Files modified:** backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py
- **Commit:** faed672

## Known Stubs

None — all columns are wired correctly. Cookie columns are nullable (no data yet; that is populated by Plan 14-02).

## Threat Surface Scan

No new trust boundaries introduced beyond those documented in the plan's threat model. The `get_current_superadmin` dependency is the only new auth path and it is documented as T-14-03.

## Self-Check: PASSED

- [x] backend/app/models/system_config.py exists
- [x] backend/alembic/versions/x6y7z8a9b0c_phase14_system_config_and_superadmin.py exists
- [x] backend/app/api/v1/deps.py contains get_current_superadmin
- [x] backend/app/schemas/user.py contains is_superuser: bool = False
- [x] backend/app/api/v1/endpoints/auth.py contains "is_superuser": user.is_superuser
- [x] Commit faed672 exists
- [x] Commit 54fd0f6 exists
