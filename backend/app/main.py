import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, RedirectResponse
from pathlib import PurePosixPath
from urllib.parse import unquote

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

from app.core.config import settings
from app.api.v1 import api_router

_FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist", "brainsuite")
)


def _run_migrations():
    logger = logging.getLogger(__name__)
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
        sync_url = os.environ.get("SYNC_DATABASE_URL", "")
        if sync_url:
            alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations complete")
    except Exception as e:
        logger.warning(f"Migration failed (non-fatal): {type(e).__name__}: {e}")


def _migrate_static_urls_to_objects():
    logger = logging.getLogger(__name__)
    sync_url = os.environ.get("SYNC_DATABASE_URL", "")
    if not sync_url:
        return
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(sync_url)
        tables_columns = [
            ("dv360_raw_performance", ["thumbnail_url", "asset_url", "video_url"]),
            ("creative_assets", ["thumbnail_url", "asset_url"]),
            ("meta_raw_performance", ["thumbnail_url", "asset_url"]),
            ("tiktok_raw_performance", ["thumbnail_url", "asset_url"]),
            ("google_ads_raw_performance", ["thumbnail_url", "video_url"]),
        ]
        total = 0
        with engine.begin() as conn:
            for table, columns in tables_columns:
                for col in columns:
                    try:
                        result = conn.execute(text(
                            f"UPDATE {table} SET {col} = REPLACE({col}, '/static/creatives/', '/objects/creatives/') "
                            f"WHERE {col} LIKE '/static/creatives/%'"
                        ))
                        if result.rowcount > 0:
                            total += result.rowcount
                            logger.info(f"  Migrated {result.rowcount} URLs in {table}.{col}")
                    except Exception:
                        pass
        if total > 0:
            logger.info(f"URL migration complete: {total} total URLs updated from /static/creatives/ to /objects/creatives/")
        else:
            logger.info("URL migration: no /static/creatives/ URLs found (already migrated or empty)")
        engine.dispose()
    except Exception as e:
        logger.warning(f"URL migration failed (non-fatal): {type(e).__name__}: {e}")


async def _background_startup():
    logger = logging.getLogger(__name__)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations)
    await loop.run_in_executor(None, _migrate_static_urls_to_objects)
    startup_delay = int(os.environ.get("SCHEDULER_STARTUP_DELAY_SECONDS", "0"))
    if startup_delay > 0:
        logger.info(f"Waiting {startup_delay}s for network readiness before starting scheduler...")
        await asyncio.sleep(startup_delay)
    try:
        from app.services.sync.scheduler import startup_scheduler
        await startup_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler startup failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_background_startup())
    yield
    task.cancel()
    try:
        from app.services.sync.scheduler import scheduler
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

_CREATIVES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "creatives"))
os.makedirs(_CREATIVES_DIR, exist_ok=True)
app.mount("/static/creatives", StaticFiles(directory=_CREATIVES_DIR), name="creatives")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/objects/{object_path:path}", include_in_schema=False)
async def serve_object(object_path: str):
    # SEC-04: Reject path traversal attempts (raw and URL-encoded variants).
    if ".." in PurePosixPath(object_path).parts:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    decoded = unquote(object_path)
    if ".." in PurePosixPath(decoded).parts:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    from app.services.object_storage import get_object_storage
    obj_storage = get_object_storage()
    relative = f"creatives/{object_path}" if not object_path.startswith("creatives/") else object_path
    is_video = relative.lower().endswith((".mp4", ".webm", ".mov", ".avi"))
    if is_video:
        signed_url = obj_storage.generate_signed_url(relative, ttl_sec=3600)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=302)
    data, content_type = obj_storage.download_blob(relative)
    if data is None:
        return Response(status_code=404, content="Not found")
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


if os.path.isdir(_FRONTEND_DIST):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve static files if they exist, otherwise serve index.html for SPA routing."""
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        no_cache_headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path, headers=no_cache_headers)
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index, headers=no_cache_headers)
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}
