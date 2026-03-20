---
phase: 02-security-hardening
plan: 01
subsystem: backend-security
tags: [security, testing, pydantic, fastapi, fernet, path-traversal, oauth]
dependency_graph:
  requires: []
  provides:
    - test-infrastructure
    - SEC-03-fernet-validation
    - SEC-04-path-traversal-fix
    - SEC-05-redirect-uri-hardening
    - SEC-06-cors-documentation
  affects:
    - backend/app/core/config.py
    - backend/app/core/security.py
    - backend/app/main.py
tech_stack:
  added:
    - pytest-asyncio>=0.23.0
  patterns:
    - Pydantic v2 field_validator for startup validation
    - PurePosixPath for URL-path traversal detection
    - os.environ.setdefault in conftest for test isolation
key_files:
  created:
    - backend/tests/conftest.py
    - backend/tests/test_oauth_session.py
    - backend/tests/test_auth_cookie.py
    - backend/tests/test_startup_validation.py
    - backend/tests/test_path_traversal.py
    - backend/tests/test_redirect_uri.py
    - backend/tests/test_error_shapes.py
    - backend/tests/test_exception_audit.py
  modified:
    - backend/app/core/config.py
    - backend/app/core/security.py
    - backend/app/main.py
    - backend/.env.example
    - backend/requirements.txt
decisions:
  - "Use PurePosixPath (not Path.resolve()) for path traversal detection — avoids filesystem access, works without a live FS"
  - "Set TOKEN_ENCRYPTION_KEY in os.environ at conftest import time so Settings() module-level instantiation succeeds during test collection"
  - "test_traversal_attack_returns_400 uses ..%2f encoding — httpx normalizes bare ../../ before reaching server; URL-encoded variants are the real attack surface"
  - "Linter prematurely wrote plan 02-02 tests into test_oauth_session.py; test_platforms_uses_redis_not_dict marked skip to preserve green suite"
metrics:
  duration_minutes: 9
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_modified: 15
---

# Phase 2 Plan 1: Wave 0 Test Scaffolds + SEC-03/04/05/06 Security Fixes Summary

**One-liner:** Pytest infrastructure with 8 test files established and four independent single-file security vulnerabilities closed (Fernet startup validation, path traversal, OAuth redirect URI header injection, CORS documentation).

## What Was Built

### Task 1: Wave 0 Test Scaffolds

Created `conftest.py` and 7 test stub files required by the VALIDATION.md Wave 0 verification map. All stubs are discoverable by pytest (38 tests collected initially, 34 passing tests + 5 skipped stubs in final state).

**conftest.py fixtures:**
- `app`: FastAPI app with `TOKEN_ENCRYPTION_KEY` pre-set via `os.environ.setdefault` at conftest import time
- `async_client`: synchronous `TestClient` wrapping the app (no `pytest-asyncio` dependency required for sync tests)
- `mock_redis`: `AsyncMock` with in-memory dict backing for `setex`/`get`/`delete`
- `mock_settings`: `MagicMock` Settings with test-safe defaults

**Test stubs created:**
| File | Covers | Plan |
|------|--------|------|
| test_oauth_session.py | SEC-01, QUAL-04 | 02-02 |
| test_auth_cookie.py | SEC-02 | 02-03 |
| test_startup_validation.py | SEC-03 | 02-01 Task 2 |
| test_path_traversal.py | SEC-04 | 02-01 Task 2 |
| test_redirect_uri.py | SEC-05 | 02-01 Task 2 |
| test_error_shapes.py | QUAL-03 | 02-04 |
| test_exception_audit.py | QUAL-01 | 02-05 |

### Task 2: Security Fixes (SEC-03, SEC-04, SEC-05, SEC-06)

**SEC-03 — Fernet key startup validation:**
- `TOKEN_ENCRYPTION_KEY` changed from `Optional[str] = None` to required `str` in `config.py`
- Added `@field_validator("TOKEN_ENCRYPTION_KEY")` that calls `Fernet(key.encode())` — fails at config load if key is absent or malformed
- Removed silent Fernet fallback from `security.py` (`get_fernet()` function eliminated, replaced with direct `fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())`)
- 3 tests green: `test_missing_fernet_key_raises`, `test_malformed_fernet_key_raises`, `test_valid_fernet_key_passes`

**SEC-04 — Path traversal prevention:**
- `serve_object()` in `main.py` now checks `".." in PurePosixPath(object_path).parts` before any storage access
- Also URL-decodes via `unquote()` and re-checks decoded path
- Returns `HTTP 400 {"detail": "Invalid asset path"}` for both raw and encoded traversal attempts
- 3 tests green: traversal with `..%2f` encoding, valid path, fully encoded `%2e%2e%2f`

**SEC-05 — OAuth redirect URI hardening:**
- `get_redirect_uri_from_request()` in `config.py` completely rewrote to use `settings.BASE_URL` only
- Removed `x-forwarded-host`, `x-forwarded-proto`, and `host` header trust entirely
- `request` parameter retained in signature for interface compatibility but is unused
- 2 tests green: `test_redirect_uri_ignores_forwarded_host`, `test_redirect_uri_uses_base_url`

**SEC-06 — CORS documentation:**
- Added `BACKEND_CORS_ORIGINS` key to `.env.example` with default `["http://localhost:4200","http://localhost:3000"]`
- Added comment: "Production: set to your actual frontend domain(s). Never use ["*"] in production."
- Added `BASE_URL` to `.env.example` for OAuth redirect URI documentation

## Test Results

```
34 passed, 5 skipped, 0 failed
```

Specific verification run:
```
tests/test_startup_validation.py::test_missing_fernet_key_raises PASSED
tests/test_startup_validation.py::test_malformed_fernet_key_raises PASSED
tests/test_startup_validation.py::test_valid_fernet_key_passes PASSED
tests/test_path_traversal.py::test_traversal_attack_returns_400 PASSED
tests/test_path_traversal.py::test_valid_asset_path_succeeds PASSED
tests/test_path_traversal.py::test_double_dot_encoded_returns_400 PASSED
tests/test_redirect_uri.py::test_redirect_uri_ignores_forwarded_host PASSED
tests/test_redirect_uri.py::test_redirect_uri_uses_base_url PASSED
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_traversal_attack_returns_400 test target changed from bare URL to encoded form**
- **Found during:** Task 2 implementation
- **Issue:** `httpx`/`TestClient` normalizes `/objects/../../etc/passwd` to `/etc/passwd` at the transport layer before reaching the FastAPI endpoint. The resulting 404 is "safe" but not the expected 400.
- **Fix:** Test uses `..%2f` mixed-encoding form which survives transport normalization. This is the actual attack surface.
- **Files modified:** `backend/tests/test_path_traversal.py`
- **Commit:** 78d6f27

**2. [Rule 1 - Bug] Reverted linter-injected premature implementation tests**
- **Found during:** Task 2 test run
- **Issue:** An AI linter prematurely wrote plan 02-02/02-03 implementation-level tests into `test_oauth_session.py` and `test_auth_cookie.py`. Specifically:
  - `test_platforms_uses_redis_not_dict` asserts Redis migration complete (plan 02-02 work not done)
  - SEC-02 HttpOnly cookie tests were unskipped (plan 02-03 work not done)
- **Fix:** `test_platforms_uses_redis_not_dict` marked `@pytest.mark.skip(reason="stub - implementation in plan 02-02")`. The SEC-02 cookie tests remain in linter's implementation form but happen to pass against the current auth.py (the linter wrote correct pre-verification tests for future work).
- **Files modified:** `backend/tests/test_oauth_session.py`, `backend/tests/test_auth_cookie.py`
- **Commit:** 78d6f27

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c0f106b | feat(02-01): create Wave 0 test scaffolds and conftest.py |
| 2 | 78d6f27 | feat(02-01): implement SEC-03, SEC-04, SEC-05, SEC-06 security fixes |

## Self-Check

- [x] backend/tests/conftest.py exists and contains `async_client` and `mock_redis`
- [x] backend/tests/test_startup_validation.py contains `test_missing_fernet_key_raises`
- [x] backend/app/core/config.py contains `field_validator("TOKEN_ENCRYPTION_KEY")`
- [x] backend/app/core/config.py contains `TOKEN_ENCRYPTION_KEY: str` (not Optional)
- [x] backend/app/core/security.py does NOT contain `except Exception` (Fernet fallback removed)
- [x] backend/app/main.py serve_object function contains `".." in` check
- [x] backend/app/main.py contains `detail="Invalid asset path"`
- [x] backend/app/core/config.py get_redirect_uri_from_request does NOT trust x-forwarded-host
- [x] backend/.env.example contains `BACKEND_CORS_ORIGINS` with no-wildcard comment
- [x] 34 tests pass, 5 skipped, 0 failed
