import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

from app.core.config import settings
from app.api.v1 import api_router

# Path to the Angular production build (works in both Docker and Replit)
_FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist", "brainsuite")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from app.services.sync.scheduler import startup_scheduler
        await startup_scheduler()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Scheduler startup failed (non-fatal): {e}")
    yield
    # Shutdown
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


# ── Serve Angular SPA (used in Replit / single-process deployments) ──────────
if os.path.isdir(_FRONTEND_DIST):
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve static files if they exist, otherwise serve index.html for SPA routing."""
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}
