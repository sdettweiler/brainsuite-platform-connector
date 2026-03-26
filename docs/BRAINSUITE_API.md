# BrainSuite API Reference

This document captures confirmed endpoint URLs, authentication details, payload shapes, and
response schemas for all BrainSuite API integrations used by the platform connector.

---

## Video API (ACE_VIDEO_SMV_API)

**Status:** Confirmed working — Phase 3 (v1.0)

### Endpoints

| Step | Method | Path |
|------|--------|------|
| Auth | POST | `https://auth.brainsuite.ai/oauth2/token` |
| Announce job | POST | `https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/announce` |
| Announce asset | POST | `https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{jobId}/assets` |
| Start job | POST | `https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{jobId}/start` |
| Poll status | GET | `https://api.brainsuite.ai/v1/jobs/ACE_VIDEO/ACE_VIDEO_SMV_API/{jobId}` |

### Response Shape

```
output.legResults[0].executiveSummary.totalScore      (float)
output.legResults[0].executiveSummary.totalRating     (string)
output.legResults[0].executiveSummary.visualizations  (dict — expires 1 hour after retrieval)
output.legResults[0].kpis[*]                          (array of dimension scores)
```

---

## Static API (ACE_STATIC_SOCIAL_STATIC_API)

**Status:** Script ready — PROD-01 auth confirmation pending (credentials not available in dev environment)

**Discovery spike script:** `scripts/spike_static_api.py`
Run with: `BRAINSUITE_CLIENT_ID=xxx BRAINSUITE_CLIENT_SECRET=yyy python scripts/spike_static_api.py`

### Base URL

```
https://api.brainsuite.ai
```

Note: The API docs reference `https://api.staging.brainsuite.ai` as the base URL for the Static API.
The production endpoint is `https://api.brainsuite.ai`. Confirm which base URL to use by running
the spike script with valid credentials.

### Authentication

- Auth endpoint: `https://auth.brainsuite.ai/oauth2/token`
- Method: OAuth 2.0 Client Credentials (`grant_type=client_credentials`)
- Credentials: Same `BRAINSUITE_CLIENT_ID` / `BRAINSUITE_CLIENT_SECRET` as video API (per D-15)
- Header format: `Authorization: Basic <base64(client_id:client_secret)>` for auth request
- Subsequent calls: `Authorization: Bearer <access_token>`
- PROD-01: Auth confirmed via discovery spike — NOTE: pending credential availability in dev environment

### Endpoints

| Step | Method | Path |
|------|--------|------|
| Announce job | POST | `/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce` |
| Announce asset | POST | `/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}/assets` |
| Start job | POST | `/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}/start` |
| Poll status | GET | `/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}` |

### Workflow: Announce → Upload → Start

Per decision D-01: use Announce→Upload→Start flow (not Create-Job URL-based flow).

**Step 1 — Announce job (POST /announce)**

Request body (briefing data goes here for Static API — NOT in /start):
```json
{
  "input": {
    "channel": "Facebook",
    "projectName": "Campaign Name",
    "assetLanguage": "en-US",
    "iconicColorScheme": "manufactory",
    "intendedMessages": ["optional message 1", "optional message 2"],
    "legs": [
      {
        "name": "image-filename.jpg",
        "staticImage": {
          "assetId": "leg1",
          "name": "image-filename.jpg"
        }
      }
    ]
  }
}
```

Response: `{"id": "<job_uuid>", "status": "Announced"}`

**Step 2 — Announce asset (POST /{jobId}/assets)**

Request body:
```json
{"assetId": "leg1", "name": "image-filename.jpg"}
```

Response: `{"assetId": "leg1", "name": "image-filename.jpg", "uploadUrl": "https://s3...", "fields": {...}}`

**Step 3 — Upload to presigned S3 URL**

Multipart POST to `uploadUrl` with `fields` dict as form fields + the file.
S3 requirement: policy fields must come before the file in the multipart form.
Expected response: HTTP 204 No Content (success).

**Step 4 — Start job (POST /{jobId}/start)**

For Static API, the briefing data is submitted in the Announce step (Step 1), NOT here.
Request body: `{}` (empty — per D-04)

Response: `{"id": "<job_uuid>", "status": "Scheduled"}`

**Step 5 — Poll (GET /{jobId})**

Poll every 30 seconds. Terminal statuses: `Succeeded`, `Failed`, `Stale`.
In-progress statuses: `Announced`, `Scheduled`, `Created`, `Started`.

### Payload Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `channel` | string | Yes | — | `"Facebook"` or `"Instagram"` only |
| `projectName` | string | Yes | — | Free text |
| `assetLanguage` | string | Yes | `"en-US"` | BCP 47 language tag |
| `iconicColorScheme` | string | No | `"manufactory"` | Confirmed valid value: `"manufactory"`. Additional values to be confirmed from spike |
| `intendedMessages` | array<string> | No | — | Max 50 words per item; split from textarea on newlines |
| `intendedMessagesLanguage` | string | Conditional | `"en-US"` | Required if `intendedMessages` provided |
| `brandValues` | array<string> | No | — | Not submitted in Phase 5 (D-13) |
| `legs[].name` | string | Yes | — | Filename |
| `legs[].staticImage.assetId` | string | Yes | — | Must match the `assetId` used in asset announce |
| `legs[].staticImage.name` | string | Yes | — | Filename with extension |

### Response Shape

Based on API docs and similarity to video API. To be confirmed with spike:
```
output.legResults[0].executiveSummary.totalScore      (float — expected, same as video)
output.legResults[0].executiveSummary.totalRating     (string — expected, same as video)
output.legResults[0].executiveSummary.visualizations  (dict — expires 1 hour after retrieval)
output.legResults[0].kpis[*]                          (array of dimension scores)
```

NOTE: Response shape not yet confirmed from live spike — pending credential availability.
Full response will be saved to `docs/spike_static_response.json` when spike runs.

### Channel Mapping for Images

The Static API `channel` field accepts: `"Facebook"` or `"Instagram"` only.
All META images map to `"Facebook"` (default) unless placement indicates Instagram.
TikTok, Google Ads, DV360 images are `UNSUPPORTED` — not submitted to Static API.

### iconicColorScheme Valid Values

- `"manufactory"` — confirmed valid from API docs
- Additional values: to be confirmed from discovery spike response
- Default used in all Phase 5 submissions: `"manufactory"`

### Rate Limiting

Same rate limit headers as video API:
- `x-ratelimit-limit`: max requests per window
- `x-ratelimit-used`: requests used in current window
- `x-ratelimit-reset`: ISO 8601 UTC reset time
- `x-ratelimit-resource`: resource the request counted against

On HTTP 429: wait until `x-ratelimit-reset` before retrying (same as video scoring service).

---

## Spike Results

**Run date:** Pending — credentials not available in dev environment
**Script:** `scripts/spike_static_api.py`
**Full response:** Will be saved to `docs/spike_static_response.json` on success

To run the spike:
```bash
# From project root:
BRAINSUITE_CLIENT_ID=<your_id> BRAINSUITE_CLIENT_SECRET=<your_secret> python scripts/spike_static_api.py
```

Update this document with actual results after running the spike in an environment with credentials.
