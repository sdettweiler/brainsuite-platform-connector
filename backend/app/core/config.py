from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
from typing import List, Optional
import os
import secrets


def _get_base_url() -> str:
    if os.environ.get("REPLIT_DEPLOYMENT") == "1":
        domain = os.environ.get("REPLIT_DOMAINS", "").split(",")[0]
    else:
        domain = os.environ.get("REPLIT_DEV_DOMAIN") or os.environ.get("REPLIT_DOMAINS", "").split(",")[0]
    if domain:
        return f"https://{domain}"
    return "http://localhost:5000"


class Settings(BaseSettings):
    APP_NAME: str = "Brainsuite Platform Connector"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql+asyncpg://brainsuite:password@localhost:5432/brainsuite_platform"
    SYNC_DATABASE_URL: str = "postgresql://brainsuite:password@localhost:5432/brainsuite_platform"

    REDIS_URL: str = "redis://localhost:6379/0"

    FRONTEND_URL: str = _get_base_url()
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200", "http://localhost:3000"]

    # Meta
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None

    # TikTok
    TIKTOK_APP_ID: Optional[str] = None
    TIKTOK_APP_SECRET: Optional[str] = None

    # Google Ads
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_DEVELOPER_TOKEN: Optional[str] = None

    # DV360
    DV360_CLIENT_ID: Optional[str] = None
    DV360_CLIENT_SECRET: Optional[str] = None

    # Currency
    EXCHANGERATE_API_KEY: Optional[str] = None
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    FRANKFURTER_API_URL: str = "https://api.frankfurter.app"

    # Token encryption
    TOKEN_ENCRYPTION_KEY: Optional[str] = None

    def get_base_url(self) -> str:
        return _get_base_url()

    def get_redirect_uri(self, platform: str) -> str:
        platform_keys = {
            "META": "meta",
            "TIKTOK": "tiktok",
            "GOOGLE_ADS": "google",
            "DV360": "dv360",
        }
        key = platform_keys.get(platform, platform.lower())
        return f"{self.get_base_url()}/api/v1/platforms/oauth/callback/{key}"

    @staticmethod
    def get_redirect_uri_from_request(request, platform: str) -> str:
        platform_keys = {
            "META": "meta",
            "TIKTOK": "tiktok",
            "GOOGLE_ADS": "google",
            "DV360": "dv360",
        }
        key = platform_keys.get(platform, platform.lower())
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        scheme = request.headers.get("x-forwarded-proto", "https")
        if host:
            base = f"{scheme}://{host}"
        else:
            base = str(request.base_url).rstrip("/")
        return f"{base}/api/v1/platforms/oauth/callback/{key}"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
