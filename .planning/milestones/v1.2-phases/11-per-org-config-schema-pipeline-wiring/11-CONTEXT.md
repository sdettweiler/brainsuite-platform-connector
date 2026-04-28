# Phase 11: Per-Org Config Schema + Pipeline Wiring - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure backend work: create `org_brainsuite_config` and `org_brainsuite_field_mappings` DB tables,
seed `brainsuite_brand_values` and `brainsuite_brand_values_language` metadata fields for all
existing orgs + new-org provisioning, and re-wire `brainsuite_score.py` /
`brainsuite_static_score.py` to read per-org credentials and app names from the DB row instead
of global `.env` settings.

No frontend work. No admin warnings or mandatory field enforcement — those are Phase 13 (PIPE-02, PIPE-03).

</domain>

<decisions>
## Implementation Decisions

### Token Caching (per-org)
- **D-01:** `BrainSuiteScoreService` keeps a single long-lived instance (as today). `self._token` / `self._token_expires_at` become dicts keyed by `org_id` (e.g. `self._tokens: dict[uuid, str]`, `self._token_expires: dict[uuid, datetime]`). Token is fetched on first use per org and cached for 50 min, exactly mirroring the current per-service caching pattern.

### Partial Config Handling
- **D-02:** Any required field on the config row being `None` (null `client_id`, `client_secret`, `video_app_name`, `static_app_name`) is treated the same as a missing row — the asset stays `UNSCORED` and no exception is raised. This also covers the case of no row at all (SC5). Required field check: `client_id`, `client_secret`, and the relevant `app_name` for the scoring endpoint type. A missing `video_app_name` must not block static scoring, and vice versa.

### Language Seed for `brainsuite_brand_values_language`
- **D-03:** Seed the exact same 31-language list already used for `brainsuite_asset_language` and `brainsuite_voice_over_language` in migration `f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py`. Values: ar, bg, cs, da, de, el, en, es, fi, fr, he, hi, hr, hu, id, it, ja, ko, ms, nl, no, pl, pt, ro, sk, sl, sv, th, tr, vi, zh. Labels match existing seed exactly.

### Migration Structure
- **D-04:** Two separate Alembic revisions:
  1. Schema migration — creates `org_brainsuite_config` and `org_brainsuite_field_mappings` tables.
  2. Seed migration — inserts `brainsuite_brand_values` (TEXT) and `brainsuite_brand_values_language` (SELECT) metadata fields for all existing orgs, plus injects them during new-org provisioning in `auth.py`.

### Client Secret Encryption
- **D-05:** Use existing `encrypt_token` / `decrypt_token` from `app.core.security` (Fernet). `client_secret_encrypted` column is `String`, encrypted at service layer — the same pattern as `access_token_encrypted` on `PlatformConnection`. Never return decrypted value to any API response.

### New-Org Provisioning Hook
- **D-06:** Inject the `brainsuite_brand_values` + `brainsuite_brand_values_language` seed inline in `auth.py` at org creation time (consistent with current pattern — no separate helper). This ensures all three org creation paths in `register` (join, create, implicit) provision the fields.

### Claude's Discretion
- Exact Alembic revision IDs / filenames (follow existing alphanumeric slug pattern)
- Whether `org_brainsuite_field_mappings` gets any constraints / indexes beyond FK (researcher/planner decide based on Phase 13 query patterns)
- Whether to extract a `_provision_org_metadata_fields()` helper within `auth.py` for reuse across the three org creation branches — planner may choose this if it reduces duplication

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Migrations (Pattern Reference)
- `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` — exact language values list to reuse; seeding pattern for `metadata_fields` + `metadata_field_values` for all existing orgs
- `backend/alembic/versions/r9s0t1u2v3w4_add_notifications_indexes.py` — most recent migration (Phase 10); new migration must chain from this revision

### Pipeline Files to Re-wire
- `backend/app/services/brainsuite_score.py` — current token auth pattern (`_get_token`), `__init__`, credential loading from `settings`
- `backend/app/services/brainsuite_static_score.py` — same pattern as above for static scoring
- `backend/app/core/config.py` — current global `BRAINSUITE_CLIENT_ID`, `BRAINSUITE_CLIENT_SECRET` settings (lines 66–84)

### New-Org Provisioning
- `backend/app/api/v1/endpoints/auth.py` — org creation paths (lines ~55–120); seed injection point

### Encryption Pattern
- `backend/app/core/security.py` — `encrypt_token` / `decrypt_token` Fernet utilities

### Models Reference
- `backend/app/models/metadata.py` — `MetadataField` + `MetadataFieldValue` models (pattern for new model files)
- `backend/app/models/scoring.py` — SQLAlchemy 2.0 Mapped types pattern (pattern for `OrgBrainsuiteConfig` model)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `encrypt_token` / `decrypt_token` (app.core.security): Drop-in for storing `client_secret_encrypted`
- `MetadataField` + `MetadataFieldValue` models: Direct pattern for the metadata seed — both table structure and Alembic seeding loop
- `BrainSuiteScoreService._get_token()`: Existing token caching logic to extend to a dict keyed by org_id

### Established Patterns
- SQLAlchemy 2.0 `Mapped[T]` + `mapped_column()` for all new model columns
- All new tables follow: UUID PK, org_id FK, `created_at` + `updated_at` timestamps, snake_case column names
- Alembic migrations use raw SQL (`sa.text(...)` with `conn.execute(...)`) for data seeds, not ORM
- `ON CONFLICT DO NOTHING` on seed inserts (idempotent re-runs)
- New-org provisioning is inline in `auth.py` `register` endpoint (no separate helper currently)

### Integration Points
- `scoring_job.py` (scheduler) calls `BrainSuiteScoreService` — must pass `org_id` or `org_config` into score service after re-wire
- `org_brainsuite_field_mappings` table is created but not populated in Phase 11 — Phase 13 owns population and enforcement

</code_context>

<specifics>
## Specific Ideas

- Language list for `brainsuite_brand_values_language` is exactly the BrainSuite-supported set already in `f2g3h4i5j6k7` — no new research needed, just copy-reference
- Token caching: dict approach means the scheduler's singleton `BrainSuiteScoreService` instance works unchanged for the rest of the pipeline; only `_get_token` internals change

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-per-org-config-schema-pipeline-wiring*
*Context gathered: 2026-04-15*
