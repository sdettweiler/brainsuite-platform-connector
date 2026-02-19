"""
YouTube / Google Ads OAuth 2.0 handler.

Auth flow:
1. Generate authorization URL pointing to Google OAuth 2.0
2. User authenticates in popup -> redirected to REDIRECT_URI with ?code=
3. Backend exchanges code for access_token + refresh_token
4. Use Google Ads API to fetch accessible customer accounts
5. User selects accounts to connect

Required scopes:
- https://www.googleapis.com/auth/adwords: Full Google Ads API access
- https://www.googleapis.com/auth/youtube.readonly: YouTube data (for video metadata)

App type: Web application (OAuth 2.0 Client)
Developer portal: https://console.developers.google.com
Additional: Google Ads API requires a Developer Token from ads.google.com

Note: YouTube ad data lives in Google Ads API (not YouTube Data API).
Use Google Ads API v15+ for all campaign/ad performance data.
"""
import httpx
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v15"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeOAuthHandler:

    def generate_auth_url(self, state: str) -> str:
        """Generate Google OAuth popup URL."""
        scope = " ".join(GOOGLE_SCOPES)
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",  # Required for refresh_token
            "prompt": "consent",  # Force consent to always get refresh_token
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
                "token_type": data.get("token_type"),
                "scope": data.get("scope"),
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired Google access token using refresh_token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()

    async def fetch_accessible_customers(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Fetch all Google Ads customer accounts accessible to this user.
        Uses the CustomerService.ListAccessibleCustomers RPC.
        """
        accounts = []
        headers = {
            "Authorization": f"Bearer {access_token}",
            "developer-token": settings.GOOGLE_DEVELOPER_TOKEN or "",
        }

        async with httpx.AsyncClient() as client:
            # List accessible customer resource names
            resp = await client.get(
                f"{GOOGLE_ADS_API_BASE}/customers:listAccessibleCustomers",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            resource_names = data.get("resourceNames", [])

            # Fetch details for each customer
            for resource_name in resource_names:
                customer_id = resource_name.split("/")[-1]
                try:
                    detail = await self._fetch_customer_details(
                        client, headers, customer_id
                    )
                    if detail:
                        accounts.append({
                            "id": customer_id,
                            "name": detail.get("descriptiveName", f"Account {customer_id}"),
                            "currency": detail.get("currencyCode", "USD"),
                            "timezone": detail.get("timeZone", "UTC"),
                            "status": "ACTIVE" if not detail.get("testAccount") else "TEST",
                            "platform": "YOUTUBE",
                        })
                except Exception as e:
                    logger.warning(f"Could not fetch details for customer {customer_id}: {e}")

        return accounts

    async def _fetch_customer_details(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        customer_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single Google Ads customer details via GAQL."""
        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone,
                customer.test_account,
                customer.status
            FROM customer
            LIMIT 1
        """
        resp = await client.post(
            f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search",
            headers={**headers, "login-customer-id": customer_id},
            json={"query": query},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", [])
        if results:
            return results[0].get("customer", {})
        return None


youtube_oauth = YouTubeOAuthHandler()
