# Platform OAuth Setup Guide

This guide provides the exact settings needed for each platform's developer portal.

---

## Meta (Facebook / Instagram)

**Portal:** https://developers.facebook.com/apps/

### App Settings
- **App type:** Business
- **Category:** Advertising

### Permissions Required (under "Products > Marketing API")
| Permission | Reason |
|---|---|
| `ads_read` | Read ad account data |
| `ads_management` | Read ad creatives |
| `business_management` | Access Business Manager accounts |
| `read_insights` | Read performance metrics |
| `pages_read_engagement` | Access page-linked ads |

### OAuth Redirect URI
Add to **Facebook Login > Settings > Valid OAuth Redirect URIs**:
```
http://localhost:8000/api/v1/platforms/oauth/callback/meta
```
For production replace `localhost:8000` with your domain.

### Scopes requested during OAuth
```
ads_read,ads_management,business_management,read_insights,pages_read_engagement
```

---

## TikTok

**Portal:** https://ads.tiktok.com/marketing_api/apps/

### App Settings
- **App type:** Web App

### Scopes Required
| Scope | Reason |
|---|---|
| `ad.read` | Read ads |
| `campaign.read` | Read campaigns |
| `report.read` | Read performance reports |

### OAuth Redirect URI
Add to **App Settings > Redirect URI**:
```
http://localhost:8000/api/v1/platforms/oauth/callback/tiktok
```

### Notes
- TikTok uses `auth_code` (not `code`) in the token exchange
- Access tokens expire after 24 hours; refresh tokens last 365 days
- Rate limit: 10 requests/second per app

---

## YouTube / Google Ads

**Portal:** https://console.developers.google.com/

### Step 1: Enable APIs
Go to **APIs & Services > Library** and enable:
1. **Google Ads API**
2. **YouTube Data API v3** (for video metadata)

### Step 2: Create OAuth 2.0 Client
Go to **APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client ID**:
- **Application type:** Web application
- **Name:** Brainsuite Platform Connector

### Authorized Redirect URIs
Add:
```
http://localhost:8000/api/v1/platforms/oauth/callback/google
```

### Step 3: Get Google Ads Developer Token
1. Log into your Google Ads manager account at https://ads.google.com
2. Go to **Tools & Settings > API Center** (under "Setup")
3. Request a Developer Token
4. For production, apply for a **Standard Access** token (Basic access has lower rate limits)

### Scopes Requested During OAuth
```
https://www.googleapis.com/auth/adwords
https://www.googleapis.com/auth/youtube.readonly
```

### Notes
- OAuth uses `access_type=offline` and `prompt=consent` to always receive a refresh_token
- Google access tokens expire after 1 hour — the app auto-refreshes them
- Google Ads API uses GAQL (Google Ads Query Language) via REST
- `cost_micros` field = actual cost × 1,000,000 (app divides by 1M automatically)
- `average_cpm` field = CPM in micros × 1,000 (app divides by 1M automatically)

---

## Production Redirect URIs

For production deployment, update the `*_REDIRECT_URI` env vars:
```
META_REDIRECT_URI=https://yourdomain.com/api/v1/platforms/oauth/callback/meta
TIKTOK_REDIRECT_URI=https://yourdomain.com/api/v1/platforms/oauth/callback/tiktok
GOOGLE_REDIRECT_URI=https://yourdomain.com/api/v1/platforms/oauth/callback/google
```

And update each platform's developer portal with the production URIs.

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your credentials

# 2. Start services
docker compose up -d

# 3. Check logs
docker compose logs -f backend

# 4. Access the app
# Frontend: http://localhost:80
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```
