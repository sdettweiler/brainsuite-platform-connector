"""
TikTok Ads OAuth 2.0 handler.

Auth flow:
1. Generate authorization URL pointing to TikTok OAuth
2. User authenticates in popup -> redirected to REDIRECT_URI with ?code=&auth_code=
3. Backend exchanges auth_code for access_token
4. Fetch advertiser accounts the user manages
5. User selects accounts to connect

Required permissions (scopes):
- ad.read: Read ad campaigns and creatives
- report.read: Read reporting data
- advertiser.read: Read advertiser account info

App type: Marketing API
Developer portal: https://ads.tiktok.com/marketing_api/apps/
Note: TikTok uses "auth_code" in callback, not "code"
"""
import httpx
import hashlib
import hmac
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

TIKTOK_AUTH_URL = "https://business-api.tiktok.com/portal/auth"
TIKTOK_TOKEN_URL = "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/"
TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

TIKTOK_SCOPES = [
    "ad.read",
    "report.read",
    "advertiser.read",
]


class TikTokOAuthHandler:

    def generate_auth_url(self, state: str) -> str:
        """Generate TikTok OAuth popup URL."""
        params = {
            "app_id": settings.TIKTOK_APP_ID,
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
            "state": state,
            "scope": ",".join(TIKTOK_SCOPES),
            "response_type": "code",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{TIKTOK_AUTH_URL}?{query}"

    async def exchange_code_for_token(self, auth_code: str) -> Dict[str, Any]:
        """Exchange TikTok auth_code for access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TIKTOK_TOKEN_URL,
                json={
                    "app_id": settings.TIKTOK_APP_ID,
                    "secret": settings.TIKTOK_APP_SECRET,
                    "auth_code": auth_code,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise ValueError(f"TikTok token exchange failed: {data.get('message')}")

            token_data = data.get("data", {})
            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data.get("scope"),
                "expires_in": token_data.get("expires_in"),
                "refresh_token_expires_in": token_data.get("refresh_token_expires_in"),
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired TikTok access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TIKTOK_API_BASE}/oauth2/refresh_token/",
                json={
                    "app_id": settings.TIKTOK_APP_ID,
                    "secret": settings.TIKTOK_APP_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise ValueError(f"TikTok token refresh failed: {data.get('message')}")
            return data.get("data", {})

    async def fetch_advertiser_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Fetch all advertiser accounts the user has access to."""
        accounts = []
        page = 1
        page_size = 100

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    f"{TIKTOK_API_BASE}/oauth2/advertiser/get/",
                    params={
                        "access_token": access_token,
                        "app_id": settings.TIKTOK_APP_ID,
                        "secret": settings.TIKTOK_APP_SECRET,
                        "page": page,
                        "page_size": page_size,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"TikTok advertiser fetch error: {data.get('message')}")
                    break

                page_info = data.get("data", {})
                advertiser_list = page_info.get("list", [])

                for advertiser in advertiser_list:
                    accounts.append({
                        "id": str(advertiser.get("advertiser_id")),
                        "name": advertiser.get("advertiser_name", ""),
                        "currency": advertiser.get("currency", "USD"),
                        "timezone": advertiser.get("timezone", "UTC"),
                        "status": advertiser.get("status", "ACTIVE"),
                        "platform": "TIKTOK",
                    })

                total_pages = page_info.get("page_info", {}).get("total_page", 1)
                if page >= total_pages:
                    break
                page += 1

        return accounts


tiktok_oauth = TikTokOAuthHandler()
