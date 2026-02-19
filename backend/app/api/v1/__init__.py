from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, platforms, dashboard, assets

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
