import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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


async def _background_startup():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations)
    try:
        from app.services.sync.scheduler import startup_scheduler
        await startup_scheduler()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Scheduler startup failed (non-fatal): {e}")


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
