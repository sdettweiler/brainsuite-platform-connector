# Phase 11: Per-Org Config Schema + Pipeline Wiring — Research

**Researched:** 2026-04-15
**Domain:** SQLAlchemy 2.0 models, Alembic migrations, BrainSuite scoring pipeline re-wire, Fernet encryption
**Confidence:** HIGH — all findings verified directly from the codebase; no external lookups required

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 Token caching:** `BrainSuiteScoreService` keeps a single long-lived instance. `self._token` / `self._token_expires_at` become dicts keyed by `org_id` — `self._tokens: dict[uuid, str]`, `self._token_expires: dict[uuid, datetime]`. Token is fetched on first use per org, cached for 50 min.
- **D-02 Partial config handling:** Any required field on the config row being `None` — or no row at all — is treated the same: asset stays `UNSCORED`, no exception raised. Required fields per endpoint type: `client_id`, `client_secret`, and the relevant `app_name` (`video_app_name` for VIDEO, `static_app_name` for STATIC_IMAGE). Missing `video_app_name` must not block static scoring.
- **D-03 Language list:** Exact 31-language list already seeded by `f2g3h4i5j6k7` for `brainsuite_asset_language` and `brainsuite_voice_over_language`. Same values, same labels.
- **D-04 Migration structure:** Two separate Alembic revisions: (1) schema — creates tables; (2) seed — inserts metadata fields + updates provisioning.
- **D-05 Client secret encryption:** Use existing `encrypt_token` / `decrypt_token` from `app.core.security` (Fernet). Column is `String`, encrypted at service layer. Never returned to any API response.
- **D-06 New-org provisioning hook:** Inject `brainsuite_brand_values` + `brainsuite_brand_values_language` seed inline in `auth.py` at org creation time, consistent with current pattern.

### Claude's Discretion

- Exact Alembic revision IDs / filenames (follow existing alphanumeric slug pattern)
- Whether `org_brainsuite_field_mappings` gets constraints / indexes beyond FK (decide based on Phase 13 query patterns)
- Whether to extract a `_provision_org_metadata_fields()` helper within `auth.py` for reuse across the three org creation branches

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FMAP-08 | `brainsuite_brand_values` (TEXT) and `brainsuite_brand_values_language` (SELECT, language enum) are seeded as default non-mandatory metadata fields for all organizations via Alembic migration and new-org provisioning | Seeding pattern fully verified in `f2g3h4i5j6k7`; language list is the existing 31-value set; new-org provisioning hook identified at `auth.py:127–154` (the `else` branch that creates roles + BrainsuiteApps) |
| PIPE-01 | Scoring pipeline reads Client ID, Client Secret, app names, and field mappings from the organization's DB config instead of global `.env` settings | `_get_token()` in both score services reads `settings.BRAINSUITE_CLIENT_ID/SECRET`; `_announce_job()` hardcodes app name in URL; both must accept org_id and look up `OrgBrainsuiteConfig` row instead; `scoring_job.py` must pass org_id into both service calls |
</phase_requirements>

---

## Summary

Phase 11 is a pure-backend data-layer and pipeline re-wiring phase. It has three distinct deliverables:

1. **Two new DB tables** — `org_brainsuite_config` (credentials + app names per org) and `org_brainsuite_field_mappings` (Phase 13 owns population; Phase 11 only creates the table schema).
2. **Two Alembic revisions** — schema migration first, then a seed migration that inserts `brainsuite_brand_values` (TEXT) and `brainsuite_brand_values_language` (SELECT) metadata fields for all existing orgs, plus new-org provisioning inline in `auth.py`.
3. **Re-wire `brainsuite_score.py` and `brainsuite_static_score.py`** — replace `settings.BRAINSUITE_CLIENT_ID/SECRET` global reads with a per-org DB lookup, and replace hardcoded app-name URL segments with the values from the DB row.

The codebase patterns are completely established: SQLAlchemy 2.0 `Mapped[T]`, Alembic raw-SQL seeds with `ON CONFLICT DO NOTHING`, Fernet encryption via `encrypt_token`/`decrypt_token`, and the singleton service pattern. No new libraries are needed.

**Primary recommendation:** Follow every existing pattern exactly — do not deviate. The only genuinely new design work is the per-org token-cache dict (D-01) and the graceful fallback path when a config row is absent or incomplete (D-02).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `org_brainsuite_config` table schema | Database / Storage | — | New SQLAlchemy model + Alembic migration |
| `org_brainsuite_field_mappings` table schema | Database / Storage | — | New SQLAlchemy model + Alembic migration (Phase 13 populates) |
| Metadata field seed (brand_values, brand_values_language) | Database / Storage | API / Backend | Alembic data migration + auth.py provisioning hook |
| Per-org credential lookup in scoring pipeline | API / Backend | Database / Storage | Service layer reads `OrgBrainsuiteConfig` row per asset org_id |
| Per-org token caching | API / Backend | — | In-memory dict on singleton service; no storage layer |
| Graceful UNSCORED fallback (no config row) | API / Backend | — | Guard in `_process_asset` / `score_asset_now` before service calls |

---

## Standard Stack

### Core (all already in use — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0 (in use) | ORM + Mapped[] column definitions | All models use it; `Mapped[T]` + `mapped_column()` pattern throughout |
| Alembic | in use | DB migrations (schema + data) | All 27 existing migrations use it; raw-SQL seed pattern established |
| cryptography (Fernet) | in use | Encrypt `client_secret_encrypted` | `encrypt_token`/`decrypt_token` already used for `access_token_encrypted` on `PlatformConnection` |
| asyncpg / psycopg2 | in use | Async + sync DB drivers | async runtime + Alembic sync env both present |
| pytest + pytest-asyncio | ≥7.4 / ≥0.23 | Unit tests | Existing test suite; `conftest.py` fully established |

**Installation:** None required — all dependencies already present.

---

## Architecture Patterns

### System Architecture Diagram

```
scoring_job.py: run_scoring_batch()
        │
        │ fetches asset + asset.organization_id
        ▼
_process_asset(score_id, asset, endpoint_type)
        │
        ├─► [NEW] Load OrgBrainsuiteConfig WHERE org_id = asset.organization_id
        │           │
        │           ├─ Row absent or required field None?
        │           │       └─► log warning, set UNSCORED, return (no exception)
        │           │
        │           └─ Row complete?
        │                   └─► decrypt client_secret, pass (client_id, client_secret, app_name)
        │                             into service call below
        │
        ├─ endpoint_type == VIDEO
        │       └─► brainsuite_score_service._get_token(org_id, client_id, client_secret)
        │                   → POST /v1/jobs/ACE_VIDEO/{video_app_name}/announce
        │                   → poll → COMPLETE / FAILED
        │
        └─ endpoint_type == STATIC_IMAGE
                └─► brainsuite_static_score_service._get_token(org_id, client_id, client_secret)
                            → POST /v1/jobs/ACE_STATIC/{static_app_name}/announce
                            → poll → COMPLETE / FAILED
```

### Recommended Project Structure (new files only)

```
backend/
├── app/
│   └── models/
│       └── brainsuite_config.py          # OrgBrainsuiteConfig + OrgBrainsuiteFieldMapping models
├── alembic/
│   └── versions/
│       ├── s0t1u2v3w4x5_add_org_brainsuite_config_tables.py   # schema migration
│       └── t1u2v3w4x5y6_seed_brand_values_metadata_fields.py  # seed migration
```

Existing files modified:
```
backend/
├── app/
│   ├── models/__init__.py                 # add OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
│   ├── services/
│   │   ├── brainsuite_score.py            # per-org token dict, org_id parameter, app_name from DB
│   │   └── brainsuite_static_score.py     # same
│   ├── services/sync/
│   │   └── scoring_job.py                 # load org config before calling services; UNSCORED fallback
│   └── api/v1/endpoints/
│       └── auth.py                        # seed brand_values fields in org creation else-branch
```

### Pattern 1: SQLAlchemy 2.0 Model (OrgBrainsuiteConfig)

**What:** New model with UUID PK, org_id FK, credential columns (client_id plain String, client_secret_encrypted String), app name columns.
**When to use:** Exactly as shown — matches `CreativeScoreResult`, `MetadataField`, and `BrainsuiteApp` patterns.

```python
# Source: backend/app/models/scoring.py + backend/app/models/platform.py (pattern)
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class OrgBrainsuiteConfig(Base):
    __tablename__ = "org_brainsuite_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client_secret_encrypted: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    video_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    static_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_org_brainsuite_config_org"),
    )
```

### Pattern 2: OrgBrainsuiteFieldMapping Model

**What:** Junction table that Phase 13 populates; Phase 11 creates schema only.
**Note on indexes (Claude's discretion):** Phase 13 queries will filter by `(org_id, app_type)` and look up by `api_field_name`. Recommend adding a composite index on `(organization_id, app_type)` now — cheap to add and avoids a separate migration later.

```python
# Source: pattern from backend/app/models/metadata.py
class OrgBrainsuiteFieldMapping(Base):
    __tablename__ = "org_brainsuite_field_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    app_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "VIDEO" or "STATIC"
    api_field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_field_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metadata_fields.id", ondelete="SET NULL"), nullable=True
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_org_brainsuite_field_mappings_org_app", "organization_id", "app_type"),
    )
```

### Pattern 3: Alembic Schema Migration

**What:** Creates both tables in a single revision chained from `r9s0t1u2v3w4`.
**When to use:** Table creation — use `op.create_table()`, not raw SQL.

```python
# Source: backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py (pattern)
revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"

def upgrade() -> None:
    op.create_table(
        "org_brainsuite_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(500), nullable=True),
        sa.Column("client_secret_encrypted", sa.String(1000), nullable=True),
        sa.Column("video_app_name", sa.String(255), nullable=True),
        sa.Column("static_app_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_org_brainsuite_config_org"),
    )
    op.create_table(
        "org_brainsuite_field_mappings",
        # ... columns ...
    )
    op.create_index(
        "ix_org_brainsuite_field_mappings_org_app",
        "org_brainsuite_field_mappings",
        ["organization_id", "app_type"],
    )
```

### Pattern 4: Alembic Seed Migration

**What:** Inserts two new metadata fields per org, exactly mirroring `f2g3h4i5j6k7`.
**Key difference from schema migration:** Uses `op.get_bind()` + `conn.execute(sa.text(...))` + `ON CONFLICT DO NOTHING`.

```python
# Source: backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py (direct pattern)
revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"

def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    now = datetime.utcnow()

    fields_def = [
        ("brainsuite_brand_values", "Brand Values", "TEXT", False, None, 8),
        ("brainsuite_brand_values_language", "Brand Values Language", "SELECT", False, None, 9),
    ]
    language_values = [
        ("ar","Arabic"), ("bg","Bulgarian"), ("cs","Czech"), ("da","Danish"),
        ("de","German"), ("el","Greek"), ("en","English"), ("es","Spanish"),
        ("fi","Finnish"), ("fr","French"), ("he","Hebrew"), ("hi","Hindi"),
        ("hr","Croatian"), ("hu","Hungarian"), ("id","Indonesian"), ("it","Italian"),
        ("ja","Japanese"), ("ko","Korean"), ("ms","Malay"), ("nl","Dutch"),
        ("no","Norwegian"), ("pl","Polish"), ("pt","Portuguese"), ("ro","Romanian"),
        ("sk","Slovak"), ("sl","Slovenian"), ("sv","Swedish"), ("th","Thai"),
        ("tr","Turkish"), ("vi","Vietnamese"), ("zh","Chinese"),
    ]

    for org_id_row in orgs:
        org_id = org_id_row[0]
        bvl_field_id = None
        for name, label, ftype, required, default, sort in fields_def:
            field_id = str(uuid.uuid4())
            conn.execute(sa.text("""
                INSERT INTO metadata_fields
                    (id, organization_id, name, label, field_type, is_required,
                     default_value, is_active, sort_order, created_at, updated_at)
                VALUES
                    (:id, :org_id, :name, :label, :ftype, :required,
                     :default_val, true, :sort, :now, :now)
                ON CONFLICT DO NOTHING
            """), {...})
            if name == "brainsuite_brand_values_language":
                bvl_field_id = field_id
        # Seed language values for brainsuite_brand_values_language
        for idx, (val, lbl) in enumerate(language_values):
            conn.execute(sa.text("""
                INSERT INTO metadata_field_values ...
                ON CONFLICT DO NOTHING  -- NOTE: metadata_field_values has no unique constraint;
                                        -- see pitfall section below
            """), {...})
```

**PITFALL NOTE on ON CONFLICT DO NOTHING for metadata_field_values:** The existing `f2g3h4i5j6k7` migration does NOT use `ON CONFLICT DO NOTHING` on `metadata_field_values` inserts (only on `metadata_fields`). This is intentional — the `metadata_field_values` table has no unique constraint that would make it idempotent. The seed migration for Phase 11 must guard against duplicate runs using the same approach: check if the field already exists via the `ON CONFLICT DO NOTHING` on `metadata_fields`, and only insert the values when the field insert succeeds (i.e., track whether the field_id is freshly inserted or was a conflict-skip). The safe pattern: always insert field_values unconditionally in the migration (idempotent re-run risk is accepted, same as `f2g3h4i5j6k7`).

### Pattern 5: Per-Org Token Cache (D-01)

**What:** Convert scalar `_token`/`_token_expires_at` to dicts keyed by `org_id`.
**Applies to:** Both `BrainSuiteScoreService` and `BrainSuiteStaticScoreService`.

```python
# Source: backend/app/services/brainsuite_score.py (existing, to be modified)

# BEFORE
def __init__(self) -> None:
    self._token: Optional[str] = None
    self._token_expires_at: Optional[datetime] = None

async def _get_token(self) -> str:
    now = datetime.now(timezone.utc)
    if self._token and self._token_expires_at and now < self._token_expires_at:
        return self._token
    client_id = settings.BRAINSUITE_CLIENT_ID or ""
    client_secret = settings.BRAINSUITE_CLIENT_SECRET or ""
    ...

# AFTER
def __init__(self) -> None:
    self._tokens: dict[str, str] = {}
    self._token_expires: dict[str, datetime] = {}

async def _get_token(self, org_id: str, client_id: str, client_secret: str) -> str:
    now = datetime.now(timezone.utc)
    if (
        org_id in self._tokens
        and org_id in self._token_expires
        and now < self._token_expires[org_id]
    ):
        return self._tokens[org_id]
    # ... fetch new token using client_id, client_secret (passed in, not from settings)
    self._tokens[org_id] = data["access_token"]
    self._token_expires[org_id] = now + timedelta(minutes=50)
    return self._tokens[org_id]

def _invalidate_token(self, org_id: str) -> None:
    self._tokens.pop(org_id, None)
    self._token_expires.pop(org_id, None)
```

**Caller change:** `_api_post_with_retry` and `poll_job_status` must receive `org_id`, `client_id`, `client_secret` and thread them into `_get_token`. Alternatively, hold them as instance-level per-call context during a single scoring run — but the simplest approach is to add them as parameters to `_get_token` and `_api_post_with_retry`.

### Pattern 6: App Name Injection into URLs

**What:** Replace hardcoded `ACE_VIDEO_SMV_API` / `ACE_STATIC_SOCIAL_STATIC_API` in URL strings with a parameter.
**Affected methods:** `_announce_job`, `_announce_asset`, `_start_job`, `poll_job_status`.

```python
# BEFORE (brainsuite_score.py)
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/announce"

# AFTER
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/{video_app_name}/announce"
```

All four URL-building methods in `BrainSuiteScoreService` reference `ACE_VIDEO_SMV_API` by string. Similarly, all four in `BrainSuiteStaticScoreService` reference `ACE_STATIC_SOCIAL_STATIC_API`. Both sets must accept the app name as a parameter.

### Pattern 7: scoring_job.py Config Lookup + Graceful Fallback (D-02)

**What:** Before calling the score service, load the org's config row and validate required fields.

```python
# Source: backend/app/services/sync/scoring_job.py (to be modified at _process_asset start)

async def _process_asset(score_id, asset: CreativeAsset, endpoint_type: str) -> None:
    # [NEW] Load org config
    org_config = None
    async with get_session_factory()() as db:
        result = await db.execute(
            select(OrgBrainsuiteConfig).where(
                OrgBrainsuiteConfig.organization_id == asset.organization_id
            )
        )
        org_config = result.scalar_one_or_none()

    # [NEW] Validate — treat absent or incomplete config as UNSCORED (D-02)
    if org_config is None:
        logger.warning(
            "Scoring skipped for asset %s: no OrgBrainsuiteConfig for org %s",
            asset.id, asset.organization_id,
        )
        await _mark_unscored(score_id)
        return

    client_id = org_config.client_id
    client_secret_enc = org_config.client_secret_encrypted
    app_name = org_config.video_app_name if endpoint_type == "VIDEO" else org_config.static_app_name

    if not client_id or not client_secret_enc or not app_name:
        logger.warning(
            "Scoring skipped for asset %s (org %s): incomplete config (missing %s)",
            asset.id, asset.organization_id,
            "client_id" if not client_id else "client_secret" if not client_secret_enc else "app_name",
        )
        await _mark_unscored(score_id)
        return

    from app.core.security import decrypt_token
    client_secret = decrypt_token(client_secret_enc)

    # ... rest of existing _process_asset logic, passing client_id/client_secret/app_name
    # into the service call ...
```

`_mark_unscored()` is a new helper alongside `_mark_failed()` — sets `scoring_status = "UNSCORED"` (resets from PENDING).

### Pattern 8: New-Org Provisioning Hook (D-06)

**What:** Add brand_values field inserts in the `else` branch of `auth.py:register` (lines ~127–154), alongside the existing `BrainsuiteApp` creation.

The three org-creation paths in `register`:
1. `org_action == "join"` → user is PENDING, no provisioning — skip
2. `org_action == "create"` → falls through to the `else` block
3. Implicit (no org_id) → also falls through to the `else` block

The existing `else` branch (line 127) covers paths 2 and 3. Inserting the metadata field seed there (consistent with D-06) covers all provisioning cases. The `join` path deliberately skips provisioning because the org already has fields seeded.

### Anti-Patterns to Avoid

- **Sharing a single token across orgs:** After re-wire, each org_id must have its own cache entry. Never fall back to `settings.BRAINSUITE_CLIENT_ID`.
- **Raising exceptions on missing config:** D-02 is explicit — no exception, asset stays UNSCORED. Exceptions would surface to the scheduler and prevent other orgs' assets from being scored.
- **Resetting PROCESSING assets:** Per project memory — never reset PROCESSING assets (they have live BrainSuite job IDs). The UNSCORED fallback in `_mark_unscored` should only transition from PENDING, not from PROCESSING.
- **ON CONFLICT targeting metadata_field_values without a unique constraint:** The table has no unique constraint; `ON CONFLICT DO NOTHING` will fail unless a target column/constraint is specified. Use conditional insert logic or accept idempotent re-run risk.
- **Returning decrypted `client_secret` in any API response:** D-05 is absolute — the encrypted column value never leaves the service layer decrypted.
- **Autogenerating Alembic revisions for data seeds:** Always write seed migrations by hand (raw SQL) — autogenerate does not detect data changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fernet encryption of client_secret | Custom encryption | `encrypt_token` / `decrypt_token` in `app.core.security` | Same pattern as `access_token_encrypted` on `PlatformConnection`; single encryption key management |
| Token expiry caching | Custom TTL class | Extend existing `_token`/`_token_expires_at` pattern to a dict (D-01) | Already battle-tested; 50 min window is established |
| Idempotent seed inserts | Custom upsert logic | `ON CONFLICT DO NOTHING` on `metadata_fields` insert | Established in all existing seed migrations |
| Alembic migration chaining | Manual dependency tracking | `down_revision = "r9s0t1u2v3w4"` on first new migration | Standard Alembic linear chain |

**Key insight:** This phase has zero need for new libraries or new patterns. Every primitive is already established in the codebase.

---

## Common Pitfalls

### Pitfall 1: Forgetting to Register New Models in `__init__.py` and `env.py`

**What goes wrong:** `OrgBrainsuiteConfig` and `OrgBrainsuiteFieldMapping` are defined but not imported in `app/models/__init__.py`. Alembic's `env.py` does `from app.models import *` — if `__init__.py` doesn't export the new models, Alembic won't see the tables and `alembic check` will show them as unapplied.
**Why it happens:** New model file added, `__init__.py` update forgotten.
**How to avoid:** Add both models to `app/models/__init__.py` and to `__all__` as part of the same task that creates the model file.
**Warning signs:** `alembic check` passes when it shouldn't; `alembic revision --autogenerate` generates a migration that creates the tables again.

### Pitfall 2: `_mark_unscored` Transition from Wrong State

**What goes wrong:** The graceful fallback sets `scoring_status = "UNSCORED"` on an asset that is currently `PROCESSING` (has a live BrainSuite job ID). This violates the project rule about never resetting PROCESSING assets.
**Why it happens:** `_process_asset` is called both by the batch (which sets PENDING first) and by `score_asset_now`. The config check happens after the PENDING transition — so the asset should be PENDING when we revert it, not PROCESSING.
**How to avoid:** The `_mark_unscored` helper should include a WHERE clause that only updates rows with `scoring_status = "PENDING"`, not PROCESSING.

### Pitfall 3: `_invalidate_token` Signature Change Breaks Retry Loop

**What goes wrong:** After converting `_invalidate_token()` to `_invalidate_token(org_id)`, the retry loop in `_api_post_with_retry` still calls the old signature, silently invalidating no-one's token.
**Why it happens:** The method signature change is not propagated to all call sites.
**How to avoid:** Grep for `_invalidate_token` in both service files before marking the task complete. The 401-retry branch in `_api_post_with_retry` must pass the same `org_id` it received.

### Pitfall 4: All Three Auth.py Org-Creation Paths

**What goes wrong:** Only the `org_action == "create"` path gets the metadata field seed; the implicit (no org_id) path is missed.
**Why it happens:** Reading `auth.py` superficially — the `elif not org_id` branch (line 72–80) also creates a new org and must provision fields.
**How to avoid:** Both the `org_action == "create"` path and the `elif not org_id` path fall through to the `else` block at line 127 — the `else` branch runs whenever `is_pending_join` is False. Verify this by tracing the `is_pending_join` variable: it is only set to True in the `join` path.
**[VERIFIED: backend/app/api/v1/endpoints/auth.py lines 44–80]** — `is_pending_join` defaults False, is only set True in the `join` branch. The `else` block at line 127 covers both create paths.

### Pitfall 5: `metadata_field_values` Idempotency in Seed Migration

**What goes wrong:** `ON CONFLICT DO NOTHING` fails on `metadata_field_values` inserts because the table has no unique constraint.
**Why it happens:** Developer copies the pattern from `metadata_fields` (which does have a unique name-per-org constraint) and applies it to `metadata_field_values` without checking.
**How to avoid:** Do not use `ON CONFLICT DO NOTHING` on `metadata_field_values` inserts. Accept that a re-run of the migration will double-insert values (same as `f2g3h4i5j6k7`), or gate the field_values inserts on a `SELECT COUNT(*)` check first.
**[VERIFIED: backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py lines 102–116]** — existing migration does NOT use ON CONFLICT for field values.

### Pitfall 6: Sort Order Collision for New Fields

**What goes wrong:** `brainsuite_brand_values` is seeded with `sort_order = 8` and `brainsuite_brand_values_language` with `sort_order = 9`. The existing fields in `f2g3h4i5j6k7` use sort orders 1–7 for video fields; `m4n5o6p7q8r9` seeded additional image fields. If those image fields used sort orders starting at 8, there will be a collision.
**How to avoid:** Check the highest sort_order used in existing migrations before choosing values. The planner should inspect `m4n5o6p7q8r9` before finalizing sort_order values.

---

## Code Examples

### Load OrgBrainsuiteConfig in scoring_job.py

```python
# Source: codebase pattern from _process_asset (backend/app/services/sync/scoring_job.py)
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.core.security import decrypt_token

async def _load_org_config(org_id) -> Optional[tuple[str, str, str, str]]:
    """Returns (client_id, client_secret, video_app_name, static_app_name) or None."""
    async with get_session_factory()() as db:
        result = await db.execute(
            select(OrgBrainsuiteConfig).where(
                OrgBrainsuiteConfig.organization_id == org_id
            )
        )
        cfg = result.scalar_one_or_none()
    if cfg is None:
        return None
    if not cfg.client_id or not cfg.client_secret_encrypted:
        return None
    return (
        cfg.client_id,
        decrypt_token(cfg.client_secret_encrypted),
        cfg.video_app_name,
        cfg.static_app_name,
    )
```

### Metadata Field Seed in auth.py

```python
# Source: backend/app/api/v1/endpoints/auth.py pattern + f2g3h4i5j6k7 seed pattern
# In the else branch (line 127+), after db.add(role):

from app.models.metadata import MetadataField, MetadataFieldValue
import uuid

brand_values_field = MetadataField(
    organization_id=org_id,
    name="brainsuite_brand_values",
    label="Brand Values",
    field_type="TEXT",
    is_required=False,
    is_active=True,
    sort_order=8,
)
db.add(brand_values_field)
await db.flush()  # get the id

bvl_field = MetadataField(
    organization_id=org_id,
    name="brainsuite_brand_values_language",
    label="Brand Values Language",
    field_type="SELECT",
    is_required=False,
    is_active=True,
    sort_order=9,
)
db.add(bvl_field)
await db.flush()

language_codes = [
    ("ar","Arabic"), ("bg","Bulgarian"), ("cs","Czech"), ("da","Danish"),
    ("de","German"), ("el","Greek"), ("en","English"), ("es","Spanish"),
    ("fi","Finnish"), ("fr","French"), ("he","Hebrew"), ("hi","Hindi"),
    ("hr","Croatian"), ("hu","Hungarian"), ("id","Indonesian"), ("it","Italian"),
    ("ja","Japanese"), ("ko","Korean"), ("ms","Malay"), ("nl","Dutch"),
    ("no","Norwegian"), ("pl","Polish"), ("pt","Portuguese"), ("ro","Romanian"),
    ("sk","Slovak"), ("sl","Slovenian"), ("sv","Swedish"), ("th","Thai"),
    ("tr","Turkish"), ("vi","Vietnamese"), ("zh","Chinese"),
]
for idx, (val, lbl) in enumerate(language_codes):
    db.add(MetadataFieldValue(
        field_id=bvl_field.id,
        value=val,
        label=lbl,
        sort_order=idx,
    ))
```

**Note:** If a `_provision_org_metadata_fields(org_id, db)` helper is extracted (Claude's discretion), the above block becomes a single call there. The planner should decide whether to inline or extract based on whether other future phases will call it.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global `settings.BRAINSUITE_CLIENT_ID` | Per-org `OrgBrainsuiteConfig` row | Phase 11 | Multiple orgs can have different BrainSuite accounts |
| Hardcoded `ACE_VIDEO_SMV_API` in URL | `video_app_name` from DB row | Phase 11 | Orgs can target different BrainSuite apps |
| Single `_token` scalar in service | Dict `_tokens[org_id]` | Phase 11 | Token pool scales with number of active orgs |

**Deprecated after Phase 11:**
- `settings.BRAINSUITE_CLIENT_ID` / `settings.BRAINSUITE_CLIENT_SECRET` — still in `config.py` (for backward compat, do NOT remove in Phase 11; they become unused but removal requires confirming no other callers). Phase 12 admin UI will manage credentials via DB only. Planner should note this as a deferred cleanup.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `metadata_field_values` has no unique constraint, making `ON CONFLICT DO NOTHING` inapplicable | Pitfall 5 | If a unique constraint was added later, the seed migration would need different handling |
| A2 | `sort_order` 8 and 9 do not collide with fields seeded by `m4n5o6p7q8r9` (image metadata fields) | Pattern 4 / Pitfall 6 | Sort order collision is cosmetic (UI ordering), not functional; low risk but worth checking before coding |

**Note:** A1 is verified by reading `metadata.py` — `MetadataFieldValue` has no `UniqueConstraint`. A2 requires reading `m4n5o6p7q8r9` to confirm — flagged as ASSUMED pending planner check. [ASSUMED]

---

## Open Questions (RESOLVED)

1. **Sort order for new metadata fields**
   - What we know: Existing video fields use sort orders 1–7 (from `f2g3h4i5j6k7`).
   - What's unclear: What sort orders did `m4n5o6p7q8r9` use for image-specific fields?
   - RESOLVED: `m4n5o6p7q8r9` uses sort 8 (`brainsuite_intended_messages`) and 9 (`brainsuite_iconic_color_scheme`). New fields get sort_order 10 (`brainsuite_brand_values`) and 11 (`brainsuite_brand_values_language`).

2. **`_provision_org_metadata_fields()` helper extraction**
   - What we know: Auth.py has three org creation branches; the `else` block covers two. Claude's discretion per CONTEXT.md.
   - What's unclear: Whether Phase 12 or 13 will add more provisioning steps that would benefit from a helper.
   - RESOLVED: Inline provisioning chosen per D-06 and existing `auth.py` pattern. No helper extracted in Phase 11. Planner confirmed this matches the existing pattern.

3. **Backward-compat for `settings.BRAINSUITE_CLIENT_ID/SECRET`**
   - What we know: These settings remain in `config.py` but become unused after Phase 11.
   - What's unclear: Whether any other endpoint (outside scoring) reads them.
   - RESOLVED: No other callers found (grep confirms only `config.py`, `brainsuite_score.py`, and `brainsuite_static_score.py` reference these settings). Settings are NOT removed in Phase 11 — deferred to Phase 12 cleanup after UI confirmation.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 11 is pure backend code and migration changes. No external tools or services beyond the existing PostgreSQL/Redis/Docker stack (already operational per v1.1 completion) are required.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ with pytest-asyncio 0.23+ |
| Config file | None — discovered via `tests/` directory convention |
| Quick run command | `cd backend && python -m pytest tests/test_scoring_pipeline_per_org.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FMAP-08 | `brainsuite_brand_values` MetadataField model has field_type=TEXT, is_required=False | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_brand_values_field_definition -x` | Wave 0 |
| FMAP-08 | `brainsuite_brand_values_language` MetadataField model has field_type=SELECT, 31 language values | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_brand_values_language_field_definition -x` | Wave 0 |
| PIPE-01 | `_get_token(org_id, client_id, client_secret)` uses passed-in credentials, caches by org_id | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_per_org_token_caching -x` | Wave 0 |
| PIPE-01 | Two orgs with different credentials fetch two independent tokens | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_two_org_tokens_independent -x` | Wave 0 |
| PIPE-01 (SC5) | Asset for org with no config row stays UNSCORED, no exception raised | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_no_config_row_stays_unscored -x` | Wave 0 |
| PIPE-01 (SC5) | Asset for org with null client_id stays UNSCORED | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_null_client_id_stays_unscored -x` | Wave 0 |
| PIPE-01 (SC5) | Missing video_app_name does not block static scoring | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_missing_video_name_allows_static -x` | Wave 0 |
| PIPE-01 | app_name from DB row used in announce URL, not hardcoded constant | unit | `pytest tests/test_scoring_pipeline_per_org.py::test_app_name_from_db_in_url -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/test_scoring_pipeline_per_org.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_scoring_pipeline_per_org.py` — covers all 8 test cases above (new file)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Pipeline uses machine-to-machine OAuth; no human auth in this phase |
| V3 Session Management | no | No session changes |
| V4 Access Control | no | No new API endpoints exposing config in this phase |
| V5 Input Validation | no | No user input; data flows from DB row to HTTP header |
| V6 Cryptography | yes | Fernet via `encrypt_token`/`decrypt_token` — never hand-roll; key validated at startup |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| client_secret leaked in API response | Information Disclosure | Never return `client_secret_encrypted` or its decrypted form in any API response (D-05) |
| client_secret leaked in logs | Information Disclosure | Never log `client_secret` or `client_secret_encrypted`; only log `client_id[:8]` truncated prefix (existing pattern in `brainsuite_score.py:64`) |
| Fernet key rotation breaks all existing secrets | Tampering | Out of scope for Phase 11; key rotation is a platform-ops concern, not this phase |

---

## Sources

### Primary (HIGH confidence — verified by direct codebase read)

- `backend/app/services/brainsuite_score.py` — full service class, `_get_token`, credential loading, URL patterns
- `backend/app/services/brainsuite_static_score.py` — full service class, same patterns
- `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` — exact seed pattern, language list
- `backend/alembic/versions/r9s0t1u2v3w4_add_notifications_indexes.py` — current HEAD revision to chain from
- `backend/app/api/v1/endpoints/auth.py` — org creation paths, provisioning hook location
- `backend/app/core/security.py` — `encrypt_token`/`decrypt_token` Fernet utilities
- `backend/app/models/scoring.py` — SQLAlchemy 2.0 model pattern
- `backend/app/models/metadata.py` — MetadataField + MetadataFieldValue pattern (no unique constraint on values)
- `backend/app/models/platform.py` — `access_token_encrypted` column pattern
- `backend/app/services/sync/scoring_job.py` — `_process_asset`, session management, `_mark_failed` helper pattern
- `backend/app/models/__init__.py` — model registration pattern
- `backend/alembic/env.py` — `from app.models import *` autogenerate hook
- `backend/tests/conftest.py` — test fixture infrastructure

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already in use; versions verified in requirements.txt
- Architecture: HIGH — all patterns verified by direct codebase read; no external research needed
- Pitfalls: HIGH — derived from codebase inspection; two flagged as ASSUMED (A2) where a single file was not read

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable codebase; no fast-moving dependencies)
