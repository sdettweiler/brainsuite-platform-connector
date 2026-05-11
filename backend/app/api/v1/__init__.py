from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, platforms, dashboard, assets, scoring, brainsuite_config, super_admin, jobs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(brainsuite_config.router, prefix="/brainsuite-config", tags=["brainsuite-config"])
api_router.include_router(super_admin.router, prefix="/super-admin", tags=["super-admin"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
