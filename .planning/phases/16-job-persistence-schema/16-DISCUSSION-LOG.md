# Phase 16: Job Persistence Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 16-job-persistence-schema
**Areas discussed:** Schema completeness, job_type column type, Autovacuum tuning, Cleanup job scheduling

---

## Schema Completeness

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add connection_id now | nullable FK → platform_connections.id; Phase 17 can link sync/download jobs without a second migration | ✓ |
| No, org_id only | Strictly match JOBS-01 spec; add connection_id in Phase 17 if needed | |

**User's choice:** Add nullable platform_connection_id now

---

| Option | Description | Selected |
|--------|-------------|----------|
| Separate metadata JSONB column | metadata = external IDs envelope; output = job payload | ✓ |
| Single output JSONB for everything | Store external IDs inside output alongside payload | |

**User's choice:** Separate metadata JSONB (metadata for IDs, output for payload)

---

| Option | Description | Selected |
|--------|-------------|----------|
| JSONB error column | {message, traceback, exception_type} — structured for Phase 19 drill-in | ✓ |
| Text column like SyncJob | Plain string, simpler, consistent with existing SyncJob.error_message | |

**User's choice:** JSONB error column

---

## job_type Column Type

| Option | Description | Selected |
|--------|-------------|----------|
| VARCHAR(50) like SyncJob | Consistent with existing model; no migration needed for new types | ✓ |
| PostgreSQL ENUM | Type-safe at DB level; requires ALTER TYPE migration for new values | |

**User's choice:** VARCHAR(50)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Composite (org_id, status) + (org_id, job_type, started_at) | Two composite indexes covering main UI query patterns | ✓ |
| Single-column indexes on org_id, status, job_type | Three separate indexes; PostgreSQL can combine via bitmap scan | |
| Let planner decide | Defer index specification to planner | |

**User's choice:** Two composite indexes

---

## Autovacuum Tuning

| Option | Description | Selected |
|--------|-------------|----------|
| Migration SQL via postgresql_with | Applied at creation time in op.create_table(); visible in pg_class | ✓ |
| SQLAlchemy __table_args__ | Readable alongside model; requires repetition in migration | |
| Separate ALTER TABLE in migration | More verbose; harder to autogenerate | |

**User's choice:** Migration SQL via postgresql_with

---

| Option | Description | Selected |
|--------|-------------|----------|
| Aggressive: vacuum 5%, analyze 2% | Good balance for high-churn status-transition table | ✓ |
| Very aggressive: vacuum 1%, analyze 0.5% | Appropriate for millions of rows; likely overkill at v1.3 scale | |
| Let planner decide | Note intent, defer specific values | |

**User's choice:** vacuum_scale_factor=0.05, analyze_scale_factor=0.02

---

## Cleanup Job Scheduling

| Option | Description | Selected |
|--------|-------------|----------|
| In startup_scheduler() alongside scoring_batch | One place for all background jobs; follows established pattern | ✓ |
| In a dedicated register_maintenance_jobs() | Cleaner separation; adds indirection for a single job | |

**User's choice:** Inline in startup_scheduler()

---

| Option | Description | Selected |
|--------|-------------|----------|
| 03:00 UTC, behind SCHEDULER_ENABLED guard | Low-traffic window; disabled in dev/test like scoring_batch | ✓ |
| 02:00 UTC, always registered | Earlier window; runs in dev too | |

**User's choice:** 03:00 UTC, SCHEDULER_ENABLED guard

---

| Option | Description | Selected |
|--------|-------------|----------|
| New maintenance.py in services/sync/ | Keeps scheduler.py focused; separate home for maintenance tasks | ✓ |
| Inline in scheduler.py | Simpler; one fewer file; scheduler.py already ~1,170 lines | |

**User's choice:** New maintenance.py

---

## Claude's Discretion

- Model file location: `BackgroundJob` in new `models/jobs.py` (user selected all recommended options throughout)

## Deferred Ideas

- None — discussion stayed within phase scope
