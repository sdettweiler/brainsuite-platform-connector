from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import List, Optional
import secrets


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

    BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:8000"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200", "http://localhost:3000"]

    # S3 / MinIO
    S3_ENDPOINT_URL: Optional[str] = None
    S3_BUCKET_NAME: str = "brainsuite-assets"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # Scheduler
    SCHEDULER_STARTUP_DELAY_SECONDS: int = 0

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
    FRANKFURTER_API_URL: str = "https://api.frankfurter.dev/v1"

    # Token encryption — required; must be a valid 32-byte url-safe base64 Fernet key.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str

    @field_validator("TOKEN_ENCRYPTION_KEY")
    @classmethod
    def validate_fernet_key(cls, v: str) -> str:
        if not v:
            raise ValueError("TOKEN_ENCRYPTION_KEY is required")
        try:
            from cryptography.fernet import Fernet
            Fernet(v.encode() if isinstance(v, str) else v)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"TOKEN_ENCRYPTION_KEY is invalid (must be 32 url-safe base64 bytes): {exc}"
            ) from exc
        return v

    def get_base_url(self) -> str:
        return self.BASE_URL

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
        """Return the OAuth callback URI using settings.BASE_URL only.

        The ``request`` parameter is intentionally unused — it exists for
        interface compatibility.  Trusting request headers such as
        x-forwarded-host would allow header-injection attacks that redirect
        OAuth tokens to an attacker-controlled host (SEC-05).
        """
        platform_keys = {
            "META": "meta",
            "TIKTOK": "tiktok",
            "GOOGLE_ADS": "google",
            "DV360": "dv360",
        }
        key = platform_keys.get(platform, platform.lower())
        from urllib.parse import urlparse
        parsed = urlparse(settings.BASE_URL)
        safe_base = f"{parsed.scheme}://{parsed.netloc}"
        return f"{safe_base}/api/v1/platforms/oauth/callback/{key}"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
