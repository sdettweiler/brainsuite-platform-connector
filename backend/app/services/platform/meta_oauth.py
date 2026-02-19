"""
Meta (Facebook) Ads OAuth 2.0 handler.

Auth flow:
1. Generate authorization URL pointing to Facebook Login
2. User authenticates in popup -> redirected to REDIRECT_URI with ?code=
3. Backend exchanges code for long-lived user access token
4. Fetch ad accounts the user has access to
5. User selects accounts to connect

Required permissions (scopes):
- ads_read: Read ad account data
- ads_management: Manage ads (needed for creative asset data)
- business_management: Access Business Manager accounts
- read_insights: Read Insights API data

App type: Facebook Login for Business
Developer portal: https://developers.facebook.com
"""
import httpx
import logging
import secrets
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

META_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
META_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
META_LONG_LIVED_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
META_GRAPH_URL = "https://graph.facebook.com/v19.0"

META_SCOPES = [
    "ads_read",
    "ads_management",
    "business_management",
    "read_insights",
    "pages_read_engagement",  # For creative thumbnails
]


class MetaOAuthHandler:

    def generate_auth_url(self, state: str) -> str:
        """Generate Facebook OAuth popup URL."""
        params = {
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.META_REDIRECT_URI,
            "scope": ",".join(META_SCOPES),
            "response_type": "code",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{META_AUTH_URL}?{query}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for short-lived access token, then upgrade to long-lived."""
        async with httpx.AsyncClient() as client:
            # Step 1: Get short-lived token
            resp = await client.get(
                META_TOKEN_URL,
                params={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "redirect_uri": settings.META_REDIRECT_URI,
                    "code": code,
                },
            )
            resp.raise_for_status()
            short_lived = resp.json()
            short_token = short_lived.get("access_token")

            # Step 2: Exchange for long-lived token (60 days)
            resp2 = await client.get(
                META_LONG_LIVED_TOKEN_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "fb_exchange_token": short_token,
                },
            )
            resp2.raise_for_status()
            long_lived = resp2.json()

            return {
                "access_token": long_lived.get("access_token"),
                "token_type": long_lived.get("token_type", "bearer"),
                "expires_in": long_lived.get("expires_in"),  # seconds
            }

    async def fetch_ad_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Fetch all ad accounts the user has access to via Business Manager."""
        accounts = []
        url = f"{META_GRAPH_URL}/me/adaccounts"
        params = {
            "fields": "id,name,currency,timezone_name,account_status,business",
            "access_token": access_token,
            "limit": 200,
        }

        async with httpx.AsyncClient() as client:
            while url:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                for account in data.get("data", []):
                    accounts.append({
                        "id": account["id"].replace("act_", ""),
                        "name": account.get("name", ""),
                        "currency": account.get("currency", "USD"),
                        "timezone": account.get("timezone_name", "UTC"),
                        "status": self._map_account_status(account.get("account_status")),
                        "platform": "META",
                    })

                # Pagination
                paging = data.get("paging", {})
                next_url = paging.get("next")
                url = next_url
                params = {}  # params embedded in next URL

        return accounts

    def _map_account_status(self, status_code: Optional[int]) -> str:
        status_map = {
            1: "ACTIVE",
            2: "DISABLED",
            3: "UNSETTLED",
            7: "PENDING_RISK_REVIEW",
            8: "PENDING_SETTLEMENT",
            9: "IN_GRACE_PERIOD",
            100: "PENDING_CLOSURE",
            101: "CLOSED",
            201: "ANY_ACTIVE",
            202: "ANY_CLOSED",
        }
        return status_map.get(status_code, "UNKNOWN")

    async def get_account_details(self, access_token: str, account_id: str) -> Dict[str, Any]:
        """Fetch single ad account details."""
        clean_id = account_id.replace("act_", "")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{META_GRAPH_URL}/act_{clean_id}",
                params={
                    "fields": "id,name,currency,timezone_name,account_status",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            return resp.json()


meta_oauth = MetaOAuthHandler()
