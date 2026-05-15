# Phase 20: Proxy Download Infrastructure - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 6 (5 modified, 1 new)
**Analogs found:** 5/5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/models/system_config.py` | model | CRUD | `backend/app/models/system_config.py` (self) | exact |
| `backend/app/services/sync/dv360_sync.py` | service | file-I/O + request-response | `backend/app/services/sync/dv360_sync.py` (self, lines ~1164–1231) | exact |
| `backend/app/services/sync/google_ads_sync.py` | service | file-I/O + request-response | `backend/app/services/sync/google_ads_sync.py` (self, lines ~314–376) | exact |
| `backend/alembic/versions/[new]_add_proxy_config.py` | migration | schema | `backend/alembic/versions/z8a9b1c2d3e5_youtube_cookies_runtime_expired.py` | role-match |
| `backend/requirements.txt` | config | dependency | `backend/requirements.txt` (self) | exact |
| `docker/Dockerfile.backend` | config | dependency | `docker/Dockerfile.backend` | implicit (no changes needed) |

## Pattern Assignments

### `backend/app/models/system_config.py` (model, CRUD)

**Analog:** Self — existing SystemConfig model (singleton pattern)

**Import pattern** (lines 1–7):
```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, UniqueConstraint, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
```

**Singleton guard pattern** (lines 10–24):
```python
class SystemConfig(Base):
    """Singleton table for platform-wide configuration (system-global, not per-org).

    Unique constraint on singleton_guard ensures exactly one row.
    Uses Text type for encrypted fields since proxy URLs with credentials are ~100+ chars.
    Encryption uses the same Fernet key as Phase 12 (TOKEN_ENCRYPTION_KEY).
    """

    __tablename__ = "system_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_guard: Mapped[str] = mapped_column(String(1), unique=True, default='X', nullable=False)
    youtube_cookies_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_cookies_backup_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
```

**Column addition pattern** (add after line 31):
```python
    # NEW: Proxy configuration (Phase 20)
    proxy_url_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proxy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
```

---

### `backend/app/services/sync/dv360_sync.py` (service, file-I/O + request-response)

**Analog:** Self — existing `_download_video_asset()` method (lines ~1140–1270)

**Imports pattern** (lines 38–60):
```python
import httpx
import csv
import io
import os
import re
import logging
import asyncio
import subprocess
import json
import tempfile
import glob
import shutil
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, NamedTuple, Tuple
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.platform import PlatformConnection
from app.models.performance import Dv360RawPerformance
from app.core.security import decrypt_token
from app.services.platform.dv360_oauth import dv360_oauth
```

**Exception class pattern** (lines 63–64):
```python
class _CookiesExpiredError(Exception):
    """Raised when yt-dlp reports YouTube cookies are no longer valid."""
```

**Cookie loading pattern from DB** (lines 1103–1138, reused for proxy):
```python
async def _get_cookies_from_db(self) -> List[str]:
    """Load encrypted cookies from SystemConfig singleton.
    
    Security (T-14-10): Decrypted cookie content is never logged.
    Only decrypt failures are logged (without the cipher text).
    """
    from app.core.security import decrypt_token
    from app.db.base import get_session_factory
    from app.models.system_config import SystemConfig
    from sqlalchemy import select

    cookies = []

    try:
        async with get_session_factory()() as db:
            result = await db.execute(select(SystemConfig).limit(1))
            config = result.scalar_one_or_none()

            if config:
                if config.youtube_cookies_encrypted:
                    try:
                        cookies.append(decrypt_token(config.youtube_cookies_encrypted))
                    except Exception:
                        logger.warning("Failed to decrypt primary YouTube cookie from DB")
                if config.youtube_cookies_backup_encrypted:
                    try:
                        cookies.append(decrypt_token(config.youtube_cookies_backup_encrypted))
                    except Exception:
                        logger.warning("Failed to decrypt backup YouTube cookie from DB")
    except Exception as e:
        logger.warning("Failed to read cookies from DB, falling back to env vars: %s", e)

    # Fall back to env vars if DB is empty (per D-11 graceful migration)
    if not cookies:
        env_primary = os.environ.get("YOUTUBE_COOKIES", "").strip()
        env_backup = os.environ.get("YOUTUBE_COOKIES_BACKUP", "").strip()
        if env_primary:
            cookies.append(env_primary)
        if env_backup:
            cookies.append(env_backup)

    return cookies
```

**Download setup pattern** (lines 1140–1163, to be modified for proxy):
```python
async def _download_video_asset(
    self,
    youtube_video_id: str,
    org_id: str,
    ad_id: str,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()

    safe_id = _sanitize_for_filename(ad_id)
    filename = f"vid_dv360_{safe_id}.mp4"
    relative_path = f"creatives/{org_id}/{filename}"

    if obj_storage.file_exists(relative_path):
        return None, obj_storage.served_url(relative_path), None

    # Read cookies from DB first, fall back to env vars if DB is empty (D-11)
    cookies = await self._get_cookies_from_db()

    url = f"https://www.youtube.com/watch?v={youtube_video_id}"

    tmpdir = tempfile.mkdtemp()
    tmp_base = os.path.join(tmpdir, "video")
```

**Proxy injection pattern** (new code, follows CONTEXT.md D-02 + D-07):
```python
    # Load SystemConfig for proxy setup (D-08: IPRoyal provider)
    proxy_url = None
    proxy_enabled = False
    session_id = None
    
    try:
        from app.db.base import get_session_factory
        from app.models.system_config import SystemConfig
        from sqlalchemy import select
        import secrets
        
        async with get_session_factory()() as config_db:
            result = await config_db.execute(select(SystemConfig).limit(1))
            config = result.scalar_one_or_none()
        
        if config and config.proxy_enabled and config.proxy_url_encrypted:
            try:
                from app.core.security import decrypt_token
                proxy_url = decrypt_token(config.proxy_url_encrypted)
                proxy_enabled = True
                # Generate session ID once per job (D-07: unique per download job)
                session_id = secrets.token_urlsafe(9)
                # Modify proxy username to include session ID: "user:pass@host:port" → "user-session-ABC123:pass@host:port"
                if "@" in proxy_url:
                    user_part, host_part = proxy_url.rsplit("@", 1)
                    if "://" in user_part:
                        scheme_end = user_part.index("://") + 3
                        scheme = user_part[:scheme_end]
                        creds = user_part[scheme_end:]
                        if ":" in creds:
                            username, password = creds.split(":", 1)
                            proxy_url = f"{scheme}{username}-session-{session_id}:{password}@{host_part}"
            except Exception as proxy_err:
                logger.error("Failed to decrypt proxy URL: %s", proxy_err)
                proxy_enabled = False
                proxy_url = None
    except Exception as cfg_err:
        logger.warning("Failed to load SystemConfig for proxy: %s", cfg_err)
```

**Logger wrapper with redaction pattern** (lines 1169–1183, modified for proxy):
```python
    def _do_download_with_cookies(cookie_data: str):
        """Closure over proxy_url for logger redaction scope."""
        import yt_dlp
        import re
        
        _expired = [False]
        
        def _redact(msg: str) -> str:
            """Redact proxy credentials from log message (D-05).
            
            Pattern: "http://user:pass@geo.iproyal.com:12321" → "[PROXY:geo.iproyal.com]"
            """
            if not proxy_url:
                return msg
            # Match credentials between "://" and "@", replace with placeholder
            redacted = re.sub(
                r'(https?://)[^@/]+@',
                r'\1[PROXY:',
                msg
            )
            # Close bracket after host (before port)
            redacted = re.sub(
                r'\[PROXY:[^/:]+(:|\])',
                lambda m: m.group(0)[:-1] + "]" + m.group(1),
                redacted
            )
            return redacted

        class _YDLLogger:
            """Wrap yt-dlp logger with credential redaction (D-05, D-06)."""
            def debug(self, msg):
                if msg.startswith("[debug] "):
                    logger.debug("yt-dlp: %s", _redact(msg))
                else:
                    logger.info("yt-dlp: %s", _redact(msg))
            def info(self, msg):
                logger.info("yt-dlp: %s", _redact(msg))
            def warning(self, msg):
                if "no longer valid" in msg:
                    _expired[0] = True
                logger.warning("yt-dlp: %s", _redact(msg))
            def error(self, msg):
                if "no longer valid" in msg:
                    _expired[0] = True
                logger.error("yt-dlp: %s", _redact(msg))

        ydl_opts = {
            "outtmpl": f"{tmp_base}.%(ext)s",
            "format": "best/b",
            "quiet": True,
            "socket_timeout": 30,
            "ignore_no_formats_error": True,
            "remote_components": {"ejs:github": True},
            "logger": _YDLLogger(),
        }
        
        # Inject proxy into ydl_opts BEFORE instantiation (D-02)
        if proxy_enabled and proxy_url:
            ydl_opts["proxy"] = proxy_url
        
        # ... existing cookie file setup (lines 1199–1211) unchanged ...
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            if _expired[0]:
                raise _CookiesExpiredError("YouTube cookies are no longer valid") from e
            # Redact exception message before logging (D-06)
            redacted_error = _redact(str(e))
            logger.error("yt-dlp exception: %s", redacted_error)
            raise
        finally:
            # ... existing cleanup (lines 1220–1221) unchanged ...
            pass
```

**Retry order pattern** (lines 1224–1231, modified for proxy):
```python
    # Retry sequence with cookieless-first when proxy enabled (D-04)
    # When proxy is enabled: ["", *primary_and_backup]
    # When proxy is disabled: [*primary_and_backup] or [""] if no cookies
    attempts = cookies if cookies else [""]
    if proxy_enabled and proxy_url:
        attempts = ["", *attempts]  # Prepend cookieless attempt
    
    loop = asyncio.get_event_loop()
    try:
        for i, cookie in enumerate(attempts):
            label = "no cookies" if not cookie else ("primary" if i == 0 else "backup")
            logger.info("  Attempting DV360 video download: %s (ad=%s, cookies=%s)", youtube_video_id, ad_id, label)
            try:
                await loop.run_in_executor(None, lambda cd=cookie: _do_download_with_cookies(cd))
                # ... existing success logic ...
                break
```

---

### `backend/app/services/sync/google_ads_sync.py` (service, file-I/O + request-response)

**Analog:** Self — existing `_download_video_asset()` method (lines ~314–376)

**Structure:** Identical to DV360 sync. Apply the same modifications:
- Import `secrets` module at top (if not already imported)
- Add proxy loading code (same pattern as DV360) in the `_download_video_asset()` method
- Modify `_do_download_with_cookies()` closure: add `_redact()` helper and update `_YDLLogger` class
- Inject proxy into `ydl_opts["proxy"]` before YoutubeDL instantiation
- Modify retry attempts list: prepend `""` when proxy enabled (D-04)

All code excerpts are identical to DV360 except for log messages that reference "GoogleAds" instead of "DV360".

---

### `backend/alembic/versions/[new]_add_proxy_config.py` (migration, schema)

**Analog:** `backend/alembic/versions/z8a9b1c2d3e5_youtube_cookies_runtime_expired.py`

**Template pattern** (same structure, copied from recent migration):
```python
"""Add proxy configuration to system_config

Revision ID: [generate_new_hash]
Revises: z8a9b1c2d3e5
Create Date: 2026-05-15

Adds two new columns to system_config:
- proxy_url_encrypted (Text, nullable) — encrypted proxy URL including credentials
- proxy_enabled (Boolean, default False) — toggle to enable/disable proxy for downloads

Both default to null/false so existing deployments are unaffected; ops must
explicitly set proxy_enabled to True and provide a proxy_url_encrypted value.
"""
from alembic import op
import sqlalchemy as sa

revision = "[new_hash_e.g., a9b1c2d3e5f6]"
down_revision = "z8a9b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_url_encrypted",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "system_config",
        sa.Column(
            "proxy_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("system_config", "proxy_enabled")
    op.drop_column("system_config", "proxy_url_encrypted")
```

**Key differences from YouTube cookies migration:**
- YouTube cookies migration (z8a9b1c2d3e5) added a single Boolean column
- Proxy migration adds TWO columns (one Text for encrypted URL, one Boolean for toggle)
- Both use `nullable=True` for encrypted fields (allows disabling without data loss)
- Both use `server_default="false"` for Boolean toggle (safe default: feature disabled until ops enables it)

---

### `backend/requirements.txt` (config, dependency)

**Analog:** Self — existing requirements.txt

**Current packages** (lines 1–33):
```
fastapi==0.115.0
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.29.0
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.4.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
python-multipart==0.0.7
httpx==0.25.2
aiohttp==3.9.4
apscheduler==3.10.4
pyotp==2.9.0
openpyxl==3.1.2
reportlab==4.0.7
python-dotenv==1.0.0
psycopg2-binary==2.9.9
redis[asyncio]>=5.0.0
pytz==2023.3
cryptography==42.0.4
email-validator==2.1.0
aiofiles==23.2.1
boto3>=1.42.0
yt-dlp
imageio-ffmpeg>=0.5.1
google-genai>=1.0.0
sse-starlette==1.8.2
pytest>=7.4.0
pytest-asyncio>=0.23.0
tenacity>=8.2.0
```

**Addition pattern** (add after line 26 or as new line after yt-dlp):
```
bgutil-ytdlp-pot-provider
```

**Rationale:**
- No version pin needed (RESEARCH.md states "latest stable works")
- yt-dlp auto-detects installed plugins; bgutil auto-loads without code changes
- If a future bgutil bug is discovered, pin to a known-good version

---

### `docker/Dockerfile.backend` (config, dependency)

**Analog:** Existing Dockerfile.backend (implicit)

**No changes required.** The Dockerfile uses the standard build pattern:
```dockerfile
COPY backend/requirements.txt /app/
RUN pip install -r /app/requirements.txt
```

Since `bgutil-ytdlp-pot-provider` is added to `requirements.txt`, it will be installed automatically on next Docker build. No Dockerfile changes needed.

---

## Shared Patterns

### Credential Encryption (Reused from Phase 14)

**Source:** `backend/app/core/security.py` (lines 28–33)

**Pattern:** Use `encrypt_token()` and `decrypt_token()` from `app.core.security` for storing sensitive data

```python
from app.core.security import encrypt_token, decrypt_token

# Encrypt before storing in DB:
config.proxy_url_encrypted = encrypt_token("http://user:pass@geo.iproyal.com:12321")
await db.commit()

# Decrypt when reading from DB (in memory only):
proxy_url = decrypt_token(config.proxy_url_encrypted)

# Never log the decrypted value:
logger.info("Proxy configured: [PROXY:geo.iproyal.com]")  # Host visible, credentials hidden
```

**Apply to:** Both DV360 and Google Ads sync services (proxy URL loading)

### SystemConfig Loading Pattern

**Source:** `backend/app/services/sync/dv360_sync.py` (lines 1103–1138)

**Pattern:** Load singleton configuration from DB using async session and `select(SystemConfig).limit(1)`

```python
from app.db.base import get_session_factory
from app.models.system_config import SystemConfig
from sqlalchemy import select

async with get_session_factory()() as db:
    result = await db.execute(select(SystemConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if config:
        # Use config.proxy_enabled, config.proxy_url_encrypted, etc.
```

**Apply to:** Both sync services (proxy and session ID loading)

### yt-dlp Logger Wrapper Pattern

**Source:** `backend/app/services/sync/dv360_sync.py` (lines 1169–1183)

**Pattern:** Define logger class inside the closure of `_do_download_with_cookies` so it can access `proxy_url` for redaction

```python
def _do_download_with_cookies(cookie_data: str):
    import yt_dlp
    
    # Define _redact() helper in closure scope (has access to proxy_url)
    def _redact(msg: str) -> str:
        # Regex to replace "user:pass@" with "[PROXY:"
        # See full implementation in DV360 pattern assignment
        pass
    
    # Logger class can call _redact()
    class _YDLLogger:
        def debug(self, msg):
            logger.debug("yt-dlp: %s", _redact(msg))
        # ... all four methods call _redact() ...
    
    ydl_opts = {"logger": _YDLLogger(), ...}
```

**Apply to:** Both sync services (all four logger methods must call `_redact()`)

---

## No Analog Found

All files have direct analogs in the codebase:

| File | Role | Reason for Existing Analog |
|------|------|---------------------------|
| — | — | — |

No files require greenfield implementation. All Phase 20 work is modification of existing structures (DV360/Google Ads sync methods, SystemConfig model, Alembic migrations).

## Metadata

**Analog search scope:** Backend sync services (`backend/app/services/sync/`), database models (`backend/app/models/`), security utilities (`backend/app/core/security.py`), Alembic migrations (`backend/alembic/versions/`), Docker build configuration

**Files scanned:** 2 sync services, 1 model file, 1 security utility, 10 recent migrations, 1 requirements file

**Pattern extraction date:** 2026-05-15

**Confidence:** HIGH — all analogs directly mirror Phase 20 implementation needs (existing cookie encryption, logger wrapping, SystemConfig loading, Alembic patterns)
