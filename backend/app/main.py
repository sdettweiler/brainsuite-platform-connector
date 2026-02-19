import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api.v1 import api_router

# Path to the Angular production build (works in both Docker and Replit)
_FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist", "brainsuite")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.services.sync.scheduler import startup_scheduler
    await startup_scheduler()
    yield
    # Shutdown
    from app.services.sync.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)


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
# Mount static assets first so /assets/* is handled before the catch-all route.
# If the dist folder doesn't exist (e.g. dev-only backend), silently skip.
if os.path.isdir(_FRONTEND_DIST):
    _assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="static_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all route — serve Angular index.html for all non-API paths."""
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return {"error": "Frontend not built. Run: cd frontend && npm run build"}
