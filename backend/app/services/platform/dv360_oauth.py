"""
DV360 (Display & Video 360) OAuth 2.0 handler.

Auth flow:
1. Generate authorization URL pointing to Google OAuth 2.0
2. User authenticates in popup -> redirected to REDIRECT_URI with ?code=
3. Backend exchanges code for access_token + refresh_token
4. Use DV360 API v4 to fetch accessible advertisers
5. User selects advertisers to connect

Required scopes:
- https://www.googleapis.com/auth/display-video: DV360 management
- https://www.googleapis.com/auth/doubleclickbidmanager: Bid Manager reporting

App type: Web application (OAuth 2.0 Client)
Developer portal: https://console.developers.google.com

Note: DV360 uses separate credentials from Google Ads.
Reporting uses Bid Manager API v2 (query-based).
"""
import httpx
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DV360_API_BASE = "https://displayvideo.googleapis.com/v4"

DV360_SCOPES = [
    "https://www.googleapis.com/auth/display-video",
    "https://www.googleapis.com/auth/doubleclickbidmanager",
]


class DV360OAuthHandler:

    def generate_auth_url(self, state: str) -> str:
        """Generate Google OAuth popup URL for DV360 scopes."""
        scope = " ".join(DV360_SCOPES)
        params = {
            "client_id": settings.DV360_CLIENT_ID,
            "redirect_uri": settings.DV360_REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",
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
                    "client_id": settings.DV360_CLIENT_ID,
                    "client_secret": settings.DV360_CLIENT_SECRET,
                    "redirect_uri": settings.DV360_REDIRECT_URI,
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
        """Refresh an expired access token using refresh_token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": settings.DV360_CLIENT_ID,
                    "client_secret": settings.DV360_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            return resp.json()

    async def fetch_accessible_advertisers(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Fetch all DV360 advertisers accessible to this user.
        Uses Display & Video 360 API v4 advertisers.list.
        """
        advertisers = []
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        async with httpx.AsyncClient() as client:
            partners = await self._fetch_partners(client, headers)

            for partner in partners:
                partner_id = partner.get("partnerId")
                if not partner_id:
                    continue

                page_token = None
                while True:
                    params: Dict[str, Any] = {
                        "partnerId": partner_id,
                        "pageSize": 100,
                    }
                    if page_token:
                        params["pageToken"] = page_token

                    resp = await client.get(
                        f"{DV360_API_BASE}/advertisers",
                        headers=headers,
                        params=params,
                    )
                    if resp.status_code != 200:
                        logger.warning(f"Failed to list advertisers for partner {partner_id}: {resp.text}")
                        break

                    data = resp.json()
                    for adv in data.get("advertisers", []):
                        advertisers.append({
                            "id": adv.get("advertiserId"),
                            "name": adv.get("displayName", f"Advertiser {adv.get('advertiserId')}"),
                            "currency": adv.get("generalConfig", {}).get("currencyCode", "USD"),
                            "timezone": adv.get("generalConfig", {}).get("timeZone", "UTC"),
                            "status": adv.get("entityStatus", "ACTIVE").replace("ENTITY_STATUS_", ""),
                            "platform": "DV360",
                            "partner_id": partner_id,
                            "partner_name": partner.get("displayName", ""),
                        })

                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break

        return advertisers

    async def _fetch_partners(self, client: httpx.AsyncClient, headers: dict) -> List[Dict[str, Any]]:
        """Fetch accessible DV360 partners."""
        partners = []
        page_token = None
        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{DV360_API_BASE}/partners",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.error(f"Failed to list partners: {resp.text}")
                break

            data = resp.json()
            partners.extend(data.get("partners", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return partners


dv360_oauth = DV360OAuthHandler()
