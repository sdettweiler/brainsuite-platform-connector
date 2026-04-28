# Phase 11: Per-Org Config Schema + Pipeline Wiring - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 8 (2 new, 6 modified)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/models/brainsuite_config.py` | model | CRUD | `backend/app/models/platform.py` (`PlatformConnection`) | exact |
| `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` | migration | batch | `backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py` | exact |
| `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py` | migration | batch | `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` | exact |
| `backend/app/models/__init__.py` | config | — | itself | exact |
| `backend/app/services/brainsuite_score.py` | service | request-response | itself (per-org token dict extension) | exact |
| `backend/app/services/brainsuite_static_score.py` | service | request-response | `backend/app/services/brainsuite_score.py` | exact |
| `backend/app/services/sync/scoring_job.py` | service | batch | itself (add config lookup + UNSCORED fallback) | exact |
| `backend/app/api/v1/endpoints/auth.py` | endpoint | request-response | itself (add metadata field provisioning in `else` branch) | exact |

---

## Pattern Assignments

### `backend/app/models/brainsuite_config.py` (model, CRUD)

**Analog:** `backend/app/models/platform.py` (lines 1–65) and `backend/app/models/scoring.py` (lines 1–56)

**Imports pattern** (`platform.py` lines 1–6 / `scoring.py` lines 1–8):
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
```

**UUID PK + org_id FK + timestamps pattern** (`platform.py` `BrainsuiteApp` lines 8–21, `scoring.py` lines 27–50):
```python
class OrgBrainsuiteConfig(Base):
    __tablename__ = "org_brainsuite_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    # ... columns ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

**Encrypted credential column pattern** (`platform.py` lines 43–44):
```python
# PlatformConnection uses:
access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
# OrgBrainsuiteConfig copies this pattern for:
# client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
# client_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
# video_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
# static_app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

**Optional Mapped type pattern** (`scoring.py` lines 40–46):
```python
from typing import Optional

brainsuite_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
```

**UniqueConstraint pattern for one row per org** (`scoring.py` lines 54–56):
```python
__table_args__ = (
    UniqueConstraint("creative_asset_id", name="uq_score_per_asset"),
)
# For OrgBrainsuiteConfig: UniqueConstraint("organization_id", name="uq_brainsuite_config_per_org")
```

**Relationship back-reference pattern** (`platform.py` line 23):
```python
organization: Mapped["Organization"] = relationship("Organization", back_populates="brainsuite_apps")
```

**`OrgBrainsuiteFieldMapping` model** — use `MetadataField` as template (`metadata.py` lines 9–33). The mapping table is simpler: UUID PK, `organization_id` FK, `metadata_field_id` FK, `brainsuite_field_name` String, timestamps.

---

### `backend/alembic/versions/s0t1u2v3w4x5_add_org_brainsuite_config_tables.py` (migration, batch)

**Analog:** `backend/alembic/versions/e1f2g3h4i5j6_add_creative_score_results.py` (lines 1–74)

**Header / revision chain pattern** (lines 1–14):
```python
"""add org_brainsuite_config and org_brainsuite_field_mappings tables

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"   # <-- chains from the Phase 10 notifications migration
branch_labels = None
depends_on = None
```

**`op.create_table()` with UUID PK + FK + timestamps** (lines 18–48):
```python
def upgrade() -> None:
    op.create_table(
        "org_brainsuite_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(500), nullable=True),
        sa.Column("client_secret_encrypted", sa.Text, nullable=True),
        sa.Column("video_app_name", sa.String(255), nullable=True),
        sa.Column("static_app_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_brainsuite_config_per_org"),
    )
    op.create_index("ix_org_brainsuite_config_org_id", "org_brainsuite_config", ["organization_id"])
```

**`op.create_index()` pattern** (lines 47–48):
```python
op.create_index("ix_score_results_status", "creative_score_results", ["scoring_status"])
op.create_index("ix_score_results_asset", "creative_score_results", ["creative_asset_id"])
```

**`downgrade()` — `op.drop_index` then `op.drop_table`** (lines 56–74):
```python
def downgrade() -> None:
    op.drop_index("ix_score_results_asset", table_name="creative_score_results")
    op.drop_index("ix_score_results_status", table_name="creative_score_results")
    op.drop_table("creative_score_results")
```

---

### `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py` (migration, batch)

**Analog:** `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` (lines 1–145) — copy this file almost verbatim for the two new fields.

**Revision chain** (lines 1–14):
```python
"""seed brainsuite_brand_values metadata fields

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-04-15
"""
revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"   # <-- chains from schema migration
```

**`op.get_bind()` + raw SQL seed loop** (lines 18–131):
```python
def upgrade() -> None:
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    now = datetime.utcnow()

    fields_def = [
        ("brainsuite_brand_values", "Brand Values", "TEXT", False, None, <next_sort>),
        ("brainsuite_brand_values_language", "Brand Values Language", "SELECT", False, None, <next_sort+1>),
    ]
    # ... same loop as f2g3h4i5j6k7 lines 76–131 ...
```

**`ON CONFLICT DO NOTHING` pattern** (lines 83–99):
```python
conn.execute(sa.text("""
    INSERT INTO metadata_fields
        (id, organization_id, name, label, field_type, is_required, default_value, is_active, sort_order, created_at, updated_at)
    VALUES
        (:id, :org_id, :name, :label, :ftype, :required, :default_val, true, :sort, :now, :now)
    ON CONFLICT DO NOTHING
"""), { ... })
```

**Language values list** (lines 35–68) — copy verbatim; all 31 values are defined here:
```python
language_values = [
    ("ar", "Arabic"), ("bg", "Bulgarian"), ("cs", "Czech"), ("da", "Danish"),
    ("de", "German"), ("el", "Greek"), ("en", "English"), ("es", "Spanish"),
    ("fi", "Finnish"), ("fr", "French"), ("he", "Hebrew"), ("hi", "Hindi"),
    ("hr", "Croatian"), ("hu", "Hungarian"), ("id", "Indonesian"), ("it", "Italian"),
    ("ja", "Japanese"), ("ko", "Korean"), ("ms", "Malay"), ("nl", "Dutch"),
    ("no", "Norwegian"), ("pl", "Polish"), ("pt", "Portuguese"), ("ro", "Romanian"),
    ("sk", "Slovak"), ("sl", "Slovenian"), ("sv", "Swedish"), ("th", "Thai"),
    ("tr", "Turkish"), ("vi", "Vietnamese"), ("zh", "Chinese"),
]
```

**Seed `metadata_field_values` loop for SELECT field** (lines 101–116):
```python
for idx, (val, lbl) in enumerate(language_values):
    conn.execute(sa.text("""
        INSERT INTO metadata_field_values
            (id, field_id, value, label, sort_order, created_at)
        VALUES
            (:id, :field_id, :value, :label, :sort, :now)
    """), {
        "id": str(uuid.uuid4()),
        "field_id": field_ids["brainsuite_brand_values_language"],
        "value": val,
        "label": lbl,
        "sort": idx,
        "now": now,
    })
```

**`downgrade()` — DELETE by `name LIKE` pattern** (lines 134–145):
```python
def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM metadata_field_values
        WHERE field_id IN (
            SELECT id FROM metadata_fields WHERE name IN ('brainsuite_brand_values', 'brainsuite_brand_values_language')
        )
    """))
    conn.execute(sa.text("""
        DELETE FROM metadata_fields
        WHERE name IN ('brainsuite_brand_values', 'brainsuite_brand_values_language')
    """))
```

---

### `backend/app/models/__init__.py` (config)

**Analog:** itself (`backend/app/models/__init__.py` lines 1–27)

**Current pattern** (lines 1–27):
```python
from app.models.user import User, Organization, OrganizationRole, RefreshToken
from app.models.platform import PlatformConnection, BrainsuiteApp
# ... other imports ...
from app.models.scoring import CreativeScoreResult
from app.models.ai_inference import AIInferenceTracking

__all__ = [
    "User", "Organization", "OrganizationRole", "RefreshToken",
    # ...
    "CreativeScoreResult",
    "AIInferenceTracking",
]
```

**Add after `AIInferenceTracking` line:**
```python
from app.models.brainsuite_config import OrgBrainsuiteConfig, OrgBrainsuiteFieldMapping
# In __all__: "OrgBrainsuiteConfig", "OrgBrainsuiteFieldMapping",
```

---

### `backend/app/services/brainsuite_score.py` (service, request-response — modified)

**Analog:** itself (lines 37–82) — extend per D-01

**Current `__init__` pattern** (lines 40–43):
```python
def __init__(self) -> None:
    self._token: Optional[str] = None
    self._token_expires_at: Optional[datetime] = None
```

**Target `__init__` after D-01 re-wire:**
```python
def __init__(self) -> None:
    self._tokens: dict[str, str] = {}                    # org_id -> token
    self._token_expires: dict[str, datetime] = {}        # org_id -> expiry
```

**Current `_get_token()` pattern** (lines 48–82) — becomes `_get_token(org_id, client_id, client_secret)`:
```python
async def _get_token(self) -> str:
    now = datetime.now(timezone.utc)
    if self._token and self._token_expires_at and now < self._token_expires_at:
        return self._token

    client_id = settings.BRAINSUITE_CLIENT_ID or ""
    client_secret = settings.BRAINSUITE_CLIENT_SECRET or ""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    # ... POST to BRAINSUITE_AUTH_URL ...
    self._token = data["access_token"]
    self._token_expires_at = now + timedelta(minutes=50)
    return self._token
```

**Target `_get_token(org_id, client_id, client_secret)` pattern (after re-wire):**
```python
async def _get_token(self, org_id: str, client_id: str, client_secret: str) -> str:
    now = datetime.now(timezone.utc)
    cached = self._tokens.get(org_id)
    expires = self._token_expires.get(org_id)
    if cached and expires and now < expires:
        return cached
    # ... same POST using passed-in client_id/client_secret ...
    self._tokens[org_id] = data["access_token"]
    self._token_expires[org_id] = now + timedelta(minutes=50)
    return self._tokens[org_id]
```

**`_invalidate_token()` → `_invalidate_token(org_id)` pattern** (lines 84–87):
```python
def _invalidate_token(self) -> None:
    self._token = None
    self._token_expires_at = None
# Becomes:
def _invalidate_token(self, org_id: str) -> None:
    self._tokens.pop(org_id, None)
    self._token_expires.pop(org_id, None)
```

**`_announce_job()` hardcoded URL pattern** (lines 187–194) — replace with passed-in `app_name`:
```python
# Current:
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/announce"
# After re-wire (app_name comes from OrgBrainsuiteConfig.video_app_name):
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_VIDEO/{app_name}/announce"
```

**`_api_post_with_retry()` call chain** — all internal calls to `_get_token()` must forward `org_id, client_id, client_secret`. The retry/401/429 logic (lines 93–181) does not change.

---

### `backend/app/services/brainsuite_static_score.py` (service, request-response — modified)

**Analog:** `backend/app/services/brainsuite_score.py` — mirrors the video service exactly for this re-wire.

Apply the **identical** `__init__`, `_get_token`, and `_invalidate_token` changes as described above for `brainsuite_score.py`. The static service's `_announce_job()` uses `static_app_name` instead of `video_app_name`:

**Static `_announce_job()` URL** (brainsuite_static_score.py, analogous to line 189 of score.py):
```python
# Current (to find in brainsuite_static_score.py):
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce"
# After re-wire:
url = f"{settings.BRAINSUITE_BASE_URL}/v1/jobs/ACE_STATIC/{static_app_name}/announce"
```

---

### `backend/app/services/sync/scoring_job.py` (service, batch — modified)

**Analog:** itself (lines 165–304)

**Current `_process_asset()` entry pattern** (lines 165–176):
```python
async def _process_asset(score_id, asset: CreativeAsset, endpoint_type: str) -> None:
    """Core per-asset scoring logic — shared by batch and immediate paths."""
    asset_id = asset.id
    logger.info(
        "Scoring asset %s: endpoint_type=%s platform=%s format=%s",
        asset_id, endpoint_type,
        getattr(asset, "platform", "?"),
        getattr(asset, "asset_format", "?"),
    )
    try:
        # ... download, metadata fetch, scoring ...
```

**Target: add OrgBrainsuiteConfig lookup at top of `_process_asset()` try block, before any scoring call:**
```python
# [NEW] Load org config — early return with UNSCORED if missing/incomplete
async with get_session_factory()() as db:
    config_result = await db.execute(
        select(OrgBrainsuiteConfig)
        .where(OrgBrainsuiteConfig.organization_id == asset.organization_id)
    )
    org_config = config_result.scalar_one_or_none()

required_app_name = (
    org_config.video_app_name if endpoint_type == "VIDEO"
    else org_config.static_app_name if endpoint_type == "STATIC_IMAGE"
    else None
)
if (
    not org_config
    or not org_config.client_id
    or not org_config.client_secret_encrypted
    or not required_app_name
):
    logger.warning(
        "Scoring skipped for asset %s: OrgBrainsuiteConfig missing or incomplete for org %s",
        asset_id, asset.organization_id,
    )
    async with get_session_factory()() as db:
        score_row = await db.get(CreativeScoreResult, score_id)
        if score_row:
            score_row.scoring_status = "UNSCORED"
            score_row.error_reason = "No BrainSuite configuration for this organization."
            await db.commit()
    return

client_secret = decrypt_token(org_config.client_secret_encrypted)
```

**Passing credentials into service calls** — replace bare `brainsuite_score_service.submit_job_with_upload(...)` calls (lines 232–236, 238–248) to pass `org_id`, `client_id`, `client_secret`, `app_name`:
```python
# Current (line 232):
job_id = await brainsuite_score_service.submit_job_with_upload(
    file_bytes=file_bytes,
    filename=filename,
    briefing_data=briefing_data,
)
# After re-wire:
job_id = await brainsuite_score_service.submit_job_with_upload(
    file_bytes=file_bytes,
    filename=filename,
    briefing_data=briefing_data,
    org_id=str(asset.organization_id),
    client_id=org_config.client_id,
    client_secret=client_secret,
    app_name=org_config.video_app_name,
)
```

**`_mark_failed()` helper pattern** (lines 353–360) — no change, reuse as-is for the UNSCORED fallback path write.

**New import to add** at top of `scoring_job.py` (lines 14–31):
```python
from app.models.brainsuite_config import OrgBrainsuiteConfig
from app.core.security import decrypt_token
```

---

### `backend/app/api/v1/endpoints/auth.py` (endpoint, request-response — modified)

**Analog:** itself (lines 126–157) — the `else` branch that creates roles + BrainsuiteApps

**Existing `else` branch provisioning pattern** (lines 126–156):
```python
else:
    role = OrganizationRole(
        organization_id=org_id,
        user_id=user.id,
        role="ADMIN",
        permissions={},
    )
    db.add(role)

    from app.models.platform import BrainsuiteApp
    video_app = BrainsuiteApp(
        organization_id=org_id,
        name="Social Media Video",
        # ...
    )
    image_app = BrainsuiteApp(
        organization_id=org_id,
        name="Social Media Static",
        # ...
    )
    db.add(video_app)
    db.add(image_app)
```

**Inject metadata field provisioning inline after `db.add(image_app)` — same `else` branch:**
```python
# [NEW] Seed brainsuite_brand_values + brainsuite_brand_values_language for new org
brand_values_field = MetadataField(
    organization_id=org_id,
    name="brainsuite_brand_values",
    label="Brand Values",
    field_type="TEXT",
    is_required=False,
    default_value=None,
    is_active=True,
    sort_order=<next_sort_after_existing_fields>,
)
db.add(brand_values_field)
await db.flush()  # to get brand_values_field.id before creating SELECT values

brand_values_lang_field = MetadataField(
    organization_id=org_id,
    name="brainsuite_brand_values_language",
    label="Brand Values Language",
    field_type="SELECT",
    is_required=False,
    default_value=None,
    is_active=True,
    sort_order=<next_sort+1>,
)
db.add(brand_values_lang_field)
await db.flush()

# Seed language values for brand_values_language field
LANGUAGE_VALUES = [
    ("ar","Arabic"),("bg","Bulgarian"),("cs","Czech"),("da","Danish"),
    # ... full 31-value list from f2g3h4i5j6k7 lines 36–68 ...
]
for idx, (val, lbl) in enumerate(LANGUAGE_VALUES):
    db.add(MetadataFieldValue(
        field_id=brand_values_lang_field.id,
        value=val,
        label=lbl,
        sort_order=idx,
    ))
```

**`MetadataField` / `MetadataFieldValue` import to add** (lines 14–19):
```python
from app.models.metadata import MetadataField, MetadataFieldValue
```

**Note on three org-creation branches** (lines 57–81): only the `else` branch (`org_action == "create"` or implicit create) at line 126 needs the provisioning injection, per D-06. The `join` path (`is_pending_join = True`) does NOT provision these fields — the org already exists.

---

## Shared Patterns

### Fernet Encryption (client_secret_encrypted)
**Source:** `backend/app/core/security.py` (lines 28–33)
**Apply to:** `brainsuite_config.py` (service layer reads/writes), `scoring_job.py` (decrypts before service call)
```python
from app.core.security import encrypt_token, decrypt_token

# Store:
config.client_secret_encrypted = encrypt_token(plain_secret)

# Read (in scoring_job.py):
client_secret = decrypt_token(org_config.client_secret_encrypted)
```

### SQLAlchemy 2.0 Mapped[T] Column Pattern
**Source:** `backend/app/models/scoring.py` (lines 28–50), `backend/app/models/metadata.py` (lines 12–25)
**Apply to:** All new model columns in `brainsuite_config.py`
```python
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
organization_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
)
client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
)
```

### Alembic Raw-SQL Seed Pattern
**Source:** `backend/alembic/versions/f2g3h4i5j6k7_seed_brainsuite_metadata_fields.py` (lines 18–131)
**Apply to:** `t1u2v3w4x5y6_seed_brand_values_metadata_fields.py`
```python
conn = op.get_bind()
orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
# ... loop over orgs, INSERT with ON CONFLICT DO NOTHING ...
```

### Graceful UNSCORED Fallback (no config row)
**Source:** `backend/app/services/sync/scoring_job.py` `_mark_failed()` (lines 353+) and `score_asset_now()` UNSUPPORTED guard (lines 139–144)
**Apply to:** `scoring_job.py` `_process_asset()` — new guard block at top of try
```python
# Guard pattern from UNSUPPORTED check (lines 139–144):
if endpoint_type == "UNSUPPORTED":
    logger.warning("score_asset_now: asset %s is UNSUPPORTED, skipping", ...)
    return
# New guard mirrors this structure, but sets status back to UNSCORED instead of returning silently
```

### Singleton Service Module-Level Instance
**Source:** `backend/app/services/brainsuite_score.py` (line 641), `backend/app/services/brainsuite_static_score.py` (last line)
**Apply to:** Both score services after re-wire — singleton instance is unchanged; only instance state (token dict) changes
```python
brainsuite_score_service = BrainSuiteScoreService()
```

---

## No Analog Found

None — all files have exact or role-match analogs in the existing codebase.

---

## Metadata

**Analog search scope:** `backend/app/models/`, `backend/app/services/`, `backend/app/services/sync/`, `backend/app/api/v1/endpoints/`, `backend/alembic/versions/`, `backend/app/core/`
**Files scanned:** 14 source files read directly
**Pattern extraction date:** 2026-04-15
