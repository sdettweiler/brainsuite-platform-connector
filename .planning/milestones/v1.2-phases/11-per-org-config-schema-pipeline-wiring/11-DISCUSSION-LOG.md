# Phase 11: Per-Org Config Schema + Pipeline Wiring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 11-per-org-config-schema-pipeline-wiring
**Areas discussed:** Token caching per-org, Partial config handling, Brand values language seed, Migration structure

---

## Token Caching Per-Org

| Option | Description | Selected |
|--------|-------------|----------|
| Dict per org_id | Service stays singleton; self._tokens dict keyed by org_id. Token + expiry per org. No extra dependencies. | ✓ |
| Fresh per job, no cache | Service instantiated or token re-fetched per scoring job. Simpler but more auth API calls. | |
| Redis-backed token store | Tokens in Redis with TTL, keyed by org_id. Survives restarts but adds Redis dependency to scoring path. | |

**User's choice:** Dict per org_id (Recommended)
**Notes:** None

---

## Partial Config Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Treat null columns = no config | Any required field null → asset stays UNSCORED, no exception. Consistent with SC5. | ✓ |
| Skip only if row is missing | Only fall through if no row exists. Partial rows with null columns would cause runtime errors. | |
| You decide | Researcher + planner pick safest approach. | |

**User's choice:** Treat null columns = no config (Recommended)
**Notes:** None

---

## Brand Values Language Seed

| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive ISO list | Full practical BrainSuite-supported set (~31 languages). | |
| Minimal (en/es/de/fr) | Just 4 common languages, expandable later. | |
| Match existing language field values | Reuse same list as brainsuite_asset_language / brainsuite_voice_over_language. | ✓ |

**User's choice:** Reuse the existing BrainSuite-supported language list from f2g3h4i5j6k7 migration
**Notes:** "Use the same list as for other language fields. i.e. the Brainsuite supported languages."

---

## Migration Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate migrations | One for schema (tables), one for data seed. Cleaner rollback. Matches existing pattern. | ✓ |
| One combined migration | Schema + seed in one Alembic revision. Simpler but harder to roll back seed-only. | |

**User's choice:** Two separate migrations (Recommended)
**Notes:** None

---

## Claude's Discretion

- Exact Alembic revision IDs / filenames
- Whether `org_brainsuite_field_mappings` gets additional constraints/indexes beyond FK
- Whether to extract a `_provision_org_metadata_fields()` helper within auth.py

## Deferred Ideas

None — discussion stayed within phase scope.
