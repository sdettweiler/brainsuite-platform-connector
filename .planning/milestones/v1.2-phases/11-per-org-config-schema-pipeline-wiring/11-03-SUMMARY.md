---
phase: 11
plan: "03"
subsystem: backend-pipeline
tags: [fastapi, sqlalchemy, per-org-config, scoring-pipeline, security, token-caching]
requirements: [PIPE-01]
dependency_graph:
  requires:
    - "11-01: OrgBrainsuiteConfig model (org_brainsuite_config table)"
    - "backend/app/core/security.py: decrypt_token"
  provides:
    - "brainsuite_score.py: per-org token dict caching, parameterized credentials + app_name"
    - "brainsuite_static_score.py: identical per-org re-wire for static scoring"
    - "scoring_job.py: OrgBrainsuiteConfig lookup, graceful UNSCORED fallback, _mark_unscored helper"
    - "test_phase11_pipeline.py: 7 static analysis + instantiation unit tests"
  affects:
    - "backend/app/services/brainsuite_score.py (modified)"
    - "backend/app/services/brainsuite_static_score.py (modified)"
    - "backend/app/services/sync/scoring_job.py (modified)"
tech_stack:
  added: []
  patterns:
    - "Per-org token dict caching: _tokens[org_id] / _token_expires[org_id] (replaces scalar)"
    - "Credential threading: org_id + client_id + client_secret + app_name params on all auth-touching methods"
    - "Graceful UNSCORED fallback: _mark_unscored guards on scoring_status == PENDING (never PROCESSING)"
    - "In-memory-only secret decryption: decrypt_token called once in _process_asset, passed as parameter"
    - "Static analysis tests via pathlib.Path.read_text() + inspect.getsource() — no live DB needed"
key_files:
  created:
    - backend/tests/test_phase11_pipeline.py
  modified:
    - backend/app/services/brainsuite_score.py
    - backend/app/services/brainsuite_static_score.py
    - backend/app/services/sync/scoring_job.py
decisions:
  - "Token cache keyed by org_id string — each org gets its own cached token, no cross-org sharing possible (T-11-06)"
  - "_mark_unscored guards on scoring_status == PENDING — PROCESSING assets are never reset per project memory rule (T-11-07)"
  - "client_secret decrypted in-memory only in _process_asset, passed as positional parameter — never logged (T-11-05)"
  - "All 4 service calls (2x submit_job_with_upload, 2x poll_job_status) thread org_id, client_id, client_secret, app_name explicitly"
  - "UNSCORED fallback logs which specific field is missing (no config row / client_id / client_secret / app_name) for admin diagnostics"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-16"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 3
---

# Phase 11 Plan 03: Pipeline Re-wire (Per-Org Credentials) Summary

**One-liner:** Both BrainSuite score services re-wired to per-org token dict caching with credential + app_name threading, and scoring_job.py wired to load OrgBrainsuiteConfig from DB with graceful UNSCORED fallback on missing/incomplete config.

## What Was Built

### Task 1: Re-wire brainsuite_score.py and brainsuite_static_score.py

Both services received identical structural changes:

**`__init__`** — replaced scalar `_token`/`_token_expires_at` with dicts:
```python
self._tokens: dict[str, str] = {}           # org_id -> token
self._token_expires: dict[str, datetime] = {}  # org_id -> expiry
```

**`_get_token(org_id, client_id, client_secret)`** — now checks `self._tokens[org_id]` instead of global settings. Credentials come from parameters, not `.env`.

**`_invalidate_token(org_id)`** — pops from both dicts with `pop(org_id, None)`.

**`_api_post_with_retry`** — added `org_id`, `client_id`, `client_secret` params; threads to `_get_token` and `_invalidate_token`.

**`_announce_job`, `_announce_asset`, `_start_job`** — added `app_name` param; URL now uses `{app_name}` instead of hardcoded `ACE_VIDEO_SMV_API` / `ACE_STATIC_SOCIAL_STATIC_API`.

**`submit_job_with_upload`, `poll_job_status`** — added `org_id`, `client_id`, `client_secret`, `app_name` params.

### Task 2: Re-wire scoring_job.py

**New imports:**
```python
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.core.security import decrypt_token
```

**`_mark_unscored(score_id, error_reason)`** — new helper placed next to `_mark_failed`. Only transitions rows with `scoring_status == "PENDING"` to UNSCORED; never touches PROCESSING assets.

**`_process_asset` additions** (at top of try block):
1. DB lookup for `OrgBrainsuiteConfig` by `asset.organization_id`
2. Determine `required_app_name` based on `endpoint_type` (video vs static)
3. If any of {config row, client_id, client_secret_encrypted, required_app_name} missing → log which field, call `_mark_unscored`, return
4. `client_secret = decrypt_token(org_config.client_secret_encrypted)` — in-memory only
5. `org_id_str = str(asset.organization_id)` — threaded to all service calls

All 4 service calls updated to pass `org_id=org_id_str`, `client_id=org_config.client_id`, `client_secret=client_secret`, `app_name=org_config.{video|static}_app_name`.

### Task 3: Unit tests (test_phase11_pipeline.py)

7 tests, all pass green:

| Test | What it verifies |
|------|-----------------|
| `test_no_config_unscored` | `_mark_unscored` signature + PENDING guard + UNSCORED assignment |
| `test_partial_config_unscored` | All 3 required-field checks + endpoint_type branch + `_mark_unscored` call |
| `test_token_cache_per_org` | `BrainSuiteScoreService` has `_tokens`/`_token_expires` dicts; old scalars absent |
| `test_token_cache_per_org_static` | Same for `BrainSuiteStaticScoreService` |
| `test_no_hardcoded_app_names` | `ACE_VIDEO_SMV_API` and `ACE_STATIC_SOCIAL_STATIC_API` absent from both service files |
| `test_no_global_settings_reads` | `settings.BRAINSUITE_CLIENT_ID/SECRET` absent from both service files |
| `test_scoring_job_imports_config` | `OrgBrainsuiteConfig` and `decrypt_token` imports present in scoring_job.py |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 79d9da2 | feat(11-03): re-wire score services for per-org credentials and app_name |
| Task 2 | 79d9cea | feat(11-03): re-wire scoring_job.py to load OrgBrainsuiteConfig per org |
| Task 3 | a0a223c | test(11-03): add 7 unit tests for per-org pipeline re-wire |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints introduced. Changes affect internal scoring pipeline only.

Threat model items from plan fully addressed:
- **T-11-05** (Information Disclosure — decrypt_token): `client_secret` decrypted in-memory, passed as parameter, never logged. Logger only logs "missing client_secret" (the field name), not the value.
- **T-11-06** (Spoofing — per-org token cache): Token dict keyed by `org_id`; `_invalidate_token(org_id)` pops only that org's entry. No cross-org token sharing possible.
- **T-11-07** (Elevation of Privilege — _mark_unscored): `scoring_status == "PENDING"` guard prevents any state transition on PROCESSING assets (which hold live BrainSuite job IDs).

## Known Stubs

None — all service wiring is fully implemented. Pipeline reads real DB rows and passes real credentials. No mock data or placeholder values in production code paths.

## Self-Check: PASSED

- `backend/app/services/brainsuite_score.py` — no ACE_VIDEO_SMV_API: CONFIRMED
- `backend/app/services/brainsuite_static_score.py` — no ACE_STATIC_SOCIAL_STATIC_API: CONFIRMED
- `backend/app/services/sync/scoring_job.py` — OrgBrainsuiteConfig import: CONFIRMED
- `backend/app/services/sync/scoring_job.py` — decrypt_token import: CONFIRMED
- `backend/app/services/sync/scoring_job.py` — _mark_unscored with PENDING guard: CONFIRMED
- `backend/app/services/sync/scoring_job.py` — 4 hits for org_id=org_id_str: CONFIRMED
- `backend/tests/test_phase11_pipeline.py` — 7 tests pass green: CONFIRMED
- Commit 79d9da2 exists: CONFIRMED
- Commit 79d9cea exists: CONFIRMED
- Commit a0a223c exists: CONFIRMED
