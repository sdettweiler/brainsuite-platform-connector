---
plan: 12-02
phase: 12-credentials-app-name-settings-ui
status: complete
completed_at: 2026-04-17
commits:
  - 85c739d feat(12-02): add Pydantic schemas for brainsuite config endpoints
  - 5b86ffa feat(12-02): add brainsuite-config endpoints + router registration
  - fafa42c test(12-02): add static analysis tests for Phase 12 config endpoints
key-files:
  created:
    - backend/app/schemas/brainsuite_config.py
    - backend/app/api/v1/endpoints/brainsuite_config.py
    - backend/tests/test_phase12_endpoints.py
  modified:
    - backend/app/api/v1/__init__.py
key-decisions:
  - "Endpoints follow async FastAPI pattern from platforms.py; all 5 mutating routes use Depends(get_current_admin) per T-12-06"
  - "CredentialsResponse schema has no client_secret field — has_secret bool is the only signal (T-12-04)"
  - "rescore-all targets scoring_status == COMPLETE, never PROCESSING or PENDING (T-12-07)"
  - "test-connection checks access_token key in response body, not just HTTP 200 (Pitfall 5)"
  - "httpx timeout 15s + ConnectError caught separately with explicit message (T-12-09)"
  - "datetime.now(timezone.utc) used throughout — never deprecated datetime.utcnow()"
  - "PATCH /apps/{app_id}/system-app-name validates app.organization_id == current_user.organization_id (T-12-08)"
requirements:
  - BSCFG-01
  - BSCFG-04
  - VSAF-01
  - VSAF-02
subsystem: backend-api
tags: [credentials, brainsuite-config, api-endpoints, security, pydantic]
dependency-graph:
  requires:
    - 12-01 (OrgBrainsuiteConfig model, BrainsuiteApp.system_app_name, scoring_job re-wire)
  provides:
    - GET /api/v1/brainsuite-config/credentials
    - PUT /api/v1/brainsuite-config/credentials
    - POST /api/v1/brainsuite-config/test-connection
    - PATCH /api/v1/brainsuite-config/apps/{app_id}/system-app-name
    - POST /api/v1/brainsuite-config/rescore-all
  affects:
    - 12-03 (Angular frontend consumes all 5 endpoints)
tech-stack:
  added: []
  patterns:
    - FastAPI async router with Depends(get_current_admin) on all mutating routes
    - Fernet encrypt_token/decrypt_token for secret storage (no plain-text secret ever returned)
    - httpx.AsyncClient with 15s timeout for external BrainSuite auth call
    - Pydantic v2 BaseModel schemas with from_attributes = True
metrics:
  duration: ~15 minutes
  tasks_completed: 3
  files_created: 3
  files_modified: 1
---

# Phase 12 Plan 02: BrainSuite Config API Endpoints Summary

BrainSuite credentials + app name backend API: 5 admin-only endpoints at `/api/v1/brainsuite-config`, all with secret masking, COMPLETE-only rescore, and access_token body validation.

## What Was Built

**Task 1: Pydantic schemas (backend/app/schemas/brainsuite_config.py)**

Created 5 schema classes:
- `CredentialsResponse` — `client_id`, `has_secret`, `has_scored_assets`; no `client_secret` field (T-12-04)
- `CredentialsUpdate` — `client_id`, `client_secret` (default `""` for D-07 keep-existing semantics)
- `CredentialsSaveResponse` — `changed: bool`, `has_scored_assets: bool` for re-score dialog trigger (D-11)
- `TestConnectionResponse` — `success: bool`, `message: str`
- `SystemAppNameUpdate` — `system_app_name: Optional[str]`

**Task 2: API endpoints + router registration**

Created `backend/app/api/v1/endpoints/brainsuite_config.py` with all 5 endpoints:

- **GET /credentials** — queries `OrgBrainsuiteConfig` for org, returns `has_secret` bool (never raw value), plus `has_scored_assets` count against `CreativeScoreResult.scoring_status == "COMPLETE"`
- **PUT /credentials** — upserts config row; D-07: only encrypts+stores secret when `payload.client_secret` is non-empty; returns `changed` bool + `has_scored_assets` for re-score dialog
- **POST /test-connection** — decrypts stored secret via Fernet, builds Basic auth header, calls `settings.BRAINSUITE_AUTH_URL` with httpx (15s timeout); validates HTTP 200 AND `"access_token" in body` (Pitfall 5); catches `httpx.ConnectError` separately with human-readable message (T-12-09)
- **PATCH /apps/{app_id}/system-app-name** — validates `app.organization_id == current_user.organization_id` before update (T-12-08); returns 404 on mismatch
- **POST /rescore-all** — bulk UPDATE targeting `scoring_status == "COMPLETE"` only; never touches PROCESSING or PENDING rows (T-12-07); scoped to `current_user.organization_id`

Updated `backend/app/api/v1/__init__.py` to import `brainsuite_config` and register router at `/brainsuite-config` prefix.

**Task 3: Static analysis tests (backend/tests/test_phase12_endpoints.py)**

10 tests covering all security and correctness invariants:
1. `test_endpoint_module_exists` — module exists and defines `router`
2. `test_router_registered` — `__init__.py` imports + prefix registered
3. `test_all_endpoints_use_admin_guard` — `get_current_admin` used, no direct `get_current_user`
4. `test_secret_never_returned` — `CredentialsResponse.model_fields` has no secret fields
5. `test_rescore_targets_complete_not_scored` — `"COMPLETE"` present, no `"SCORED"` in status assignments
6. `test_rescore_does_not_touch_processing` — PROCESSING appears only in docstrings
7. `test_test_connection_checks_access_token` — `access_token` string present
8. `test_empty_secret_keeps_existing` — `if payload.client_secret:` guard present
9. `test_encrypt_decrypt_imports` — exact import statement verified
10. `test_datetime_utc_pattern` — `datetime.utcnow()` absent, `datetime.now(timezone.utc)` present

All 10 pass: `pytest tests/test_phase12_endpoints.py` exits 0.

## Deviations from Plan

None — plan executed exactly as written. The `class Config: from_attributes = True` Pydantic v2 deprecation warning (use `model_config = ConfigDict(from_attributes=True)` instead) is a pre-existing pattern in the codebase (`platform.py` uses the same style) and does not affect functionality.

## Known Stubs

None — all endpoints are fully wired to real DB models and queries. No placeholder data.

## Self-Check: PASSED

- backend/app/schemas/brainsuite_config.py — FOUND
- backend/app/api/v1/endpoints/brainsuite_config.py — FOUND
- backend/tests/test_phase12_endpoints.py — FOUND
- backend/app/api/v1/__init__.py modified — FOUND
- Commit 85c739d — FOUND
- Commit 5b86ffa — FOUND
- Commit fafa42c — FOUND
- 10/10 tests pass — VERIFIED
- 5x `Depends(get_current_admin)` — VERIFIED
- 0x `"SCORED"` in query logic — VERIFIED
