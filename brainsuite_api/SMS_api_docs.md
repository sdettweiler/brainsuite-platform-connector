# ACE Social Media Static (Seb) API - Claude Code Reference

## Overview

**API Name:** ACE Social Media Static (Seb)  
**Version:** 1.0.0  
**OpenAPI Version:** OAS 3.1  
**Purpose:** Evaluate the effectiveness of your assets in social media context  
**Base URL:** https://api.staging.brainsuite.ai

---

## Table of Contents
1. [Authentication](#authentication)
2. [Base Endpoints](#base-endpoints)
3. [API Endpoints](#api-endpoints)
4. [Data Schemas](#data-schemas)
5. [Response Codes](#response-codes)
6. [Usage Examples](#usage-examples)
7. [Important Notes](#important-notes)

---

## Authentication

The API uses bearer token authentication via the `Authorize` button in the OpenAPI interface. When making requests programmatically, include:
```
Authorization: Bearer <YOUR_API_TOKEN>
```

---

## Base Endpoints

All endpoints are prefixed with:
```
/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/
```

---

## API Endpoints

### 1. Create Job

**Endpoint:** `POST /create`  
**Description:** Create a ACE Social Media Static (Seb) job by providing assets via public URLs  
**Parameters:** None  
**Request Body Content-Type:** `application/json`

#### Request Schema: CreateJobInput
```json
{
  "input": {
    "channel": "Facebook",
    "projectName": "string",
    "assetLanguage": "en-US",
    "iconicColorScheme": "manufactory",
    "intendedMessages": [
      "string (max 50 words per item)"
    ],
    "intendedMessagesLanguage": "en-US",
    "brandValues": [
      "string (max 50 words per item)"
    ],
    "brandValuesLanguage": "en-US",
    "legs": [
      {
        "name": "string",
        "staticImage": {
          "assetId": "string",
          "name": "file_name.file_extension",
          "url": "https://example.com/path-to-publicly-available-asset",
          "assets": [
            {
              "assetId": "string",
              "name": "file_name.file_extension",
              "url": "https://example.com/path-to-publicly-available-asset"
            }
          ]
        }
      }
    ]
  }
}
```

#### Field Details:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| channel | string | Yes | - | Channel for the asset: "Facebook" or "Instagram" |
| projectName | string | Yes | - | Name of the project |
| assetLanguage | string | Yes | "en-US" | Language of the asset |
| iconicColorScheme | string | No | "manufactory" | Color scheme for the iconic asset |
| intendedMessages | array<string> | No | ["natural ingredients", "healthy"] | Messages the asset should convey (max 50 words each) |
| intendedMessagesLanguage | string | Conditional | "en-US" | Required if intendedMessages is provided |
| brandValues | array<string> | No | ["Naturalness", "Joy"] | Brand values to evaluate (max 50 words each) |
| brandValuesLanguage | string | Conditional | "en-US" | Required if brandValues is provided |
| legs | array<object> | Yes | - | Array of asset legs (1-10 items) |

#### Response: 200 OK
```json
{
  "id": "f3fa85f64-5717-4562-b3fc-2c26356caf5c"
}
```

**Response Details:** Returns the job ID for tracking the job status.

---

### 2. Announce Job

**Endpoint:** `POST /announce`  
**Description:** Announce a new ACE Social Media Static (Seb) job  
**Parameters:** None  
**Request Body Content-Type:** `application/json`

#### Request Schema: AnnounceJobInput
```json
{
  "input": {
    "channel": "Facebook",
    "projectName": "string",
    "assetLanguage": "en-US",
    "iconicColorScheme": "manufactory",
    "intendedMessages": [
      "string"
    ],
    "intendedMessagesLanguage": "en-US",
    "brandValues": [
      "string"
    ],
    "brandValuesLanguage": "en-US",
    "legs": [
      {
        "name": "string",
        "staticImage": {
          "assetId": "string",
          "name": "string",
          "url": "string",
          "assets": [
            {
              "assetId": "string",
              "name": "string",
              "url": "string"
            }
          ]
        }
      }
    ]
  }
}
```

#### Response: 200 OK
```json
{
  "id": "string",
  "msg": "string",
  "type": "string"
}
```

---

### 3. Add Assets to Announced Job

**Endpoint:** `POST /{jobId}/assets`  
**Description:** Announce a new asset for a job. Upload your asset to the provided uploadUrl after receiving it.  
**Parameters:** 
- `jobId` (path, required): UUID - Unique job identifier

#### Important Notes:
- The `uploadUrl` is valid for 5 minutes. If exceeded, create a new uploadUrl by providing the same assetId
- Make sure to use the correct assetId
- The filesize must not exceed 5GB
- Do not share the upload credentials with third parties
- You can only upload one asset per one asset announcement to match the announced assetId
- If the assetId already exists, the announced asset will be replaced instead of appended

#### Request Body:
```json
{
  "assetId": "string",
  "name": "file_name.file_extension"
}
```

#### Curl Example (Upload to uploadUrl):
```bash
curl -X POST 'https://brainsuite-frontend-file-upload.s3.amazonaws.com/' \
  -F 'key=ACE_VIDEO_X/08296d3b-93fe-49fb-81b6-37a8b8668986/assets/video.mp4' \
  -F 'x-amz-algorithm=AWS4-HMAC-SHA256' \
  -F 'x-amz-credential=XXXXXXXXXXXXXXXXXXXX/20240101/eu-central-1/s3/aws4_request' \
  -F 'x-amz-date=20240101T091919Z' \
  -F 'x-amz-security-token=XXXXXXXXXXXXXXXXXXXXXXXXXXXX...' \
  -F 'policy=XXXXXXXXXXXXXXXXXXXX...' \
  -F 'x-amz-signature=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' \
  -F 'file=@local_path_to_asset'
```

#### Response: 204 No Content

On successful upload status `204 No Content` is returned.

---

### 4. Start Announced Job

**Endpoint:** `POST /{jobId}/start`  
**Description:** Start an announced ACE Social Media Static (Seb) job  
**Parameters:**
- `jobId` (path, required): UUID - Unique job identifier

#### Request Body:
```json
{}
```

#### Response: 200 OK
```json
{
  "id": "string",
  "msg": "string",
  "type": "string"
}
```

---

### 5. Get Job Status

**Endpoint:** `GET /{jobId}`  
**Description:** Query the status and result of ACE Social Media Static (Seb) jobs  
**Parameters:**
- `jobId` (path, required): UUID - Unique job identifier

#### Response: 200 OK
```json
{
  "detail": [
    {
      "loc": [
        "string"
      ],
      "msg": "string",
      "type": "string"
    }
  ]
}
```

---

### 6. Export Cockpit

**Endpoint:** `GET /cockpit`  
**Description:** Export cockpit for ACE Social Media Static (Seb) jobs  
**Parameters:** None

#### Response Format:

**Media Type:** `application/json`

#### Example Response:

Returns aggregated data about all ACE Social Media Static jobs and their results. The format follows the CockpitFileOutputFormat schema.

---

## Data Schemas

### Core Schemas

#### CreateJobInput Schema
Main input schema for creating a new job. Contains all the parameters needed to analyze assets in social media context.

#### UploadedAssetSchema
Represents an uploaded asset with the following fields:
- `assetId` (string): Unique identifier for the asset
- `name` (string): Name of the asset including file extension (e.g., "file_name.file_extension")
- `url` (string): URL of a publicly available asset (e.g., "https://example.com/path-to-publicly-available-asset")

#### Leg Schema
Represents a creative "leg" or variant containing:
- `name` (string): Name of the leg
- `staticImage` (object): Static image asset containing assetId, name, url, and related assets array

### Enumeration Values

#### Channel Options
- "Facebook"
- "Instagram"

#### Language Options
Supported languages include: en-US, de-DE, fr-FR, es-ES, it-IT, af-ZA, ar-AE, be-BY, bg-BG, zh-CN, hr-HR, cs-CZ, da-DA, nl-NL, tl-PH, fi-FI, el-GR, hi-IN, id-ID, ja-JP, kn-IN, kk-KZ, ko-KR, lt-LT, ms-MY, pl-PL, pt-PT, ro-RO, ru-RU, sr-RS, sk-SK, sv-SE, ta-IN, th-TH, tr-TR, uk-UA, vi-VN, he-IL, bn-BD, ur-PK, km-KH

#### Color Scheme Options
- "manufactory"

---

## Response Codes

| Code | Description | Details |
|------|-------------|---------|
| 200 | Successful Operation | Request completed successfully |
| 201 | Created | Resource created successfully |
| 204 | No Content | Successful operation with no response body (used for file uploads) |
| 400 | Bad Request | Invalid request parameters or missing required fields |
| 401 | Unauthorized | Invalid or missing authentication token |
| 404 | Not Found | Job ID or resource not found |
| 422 | Unprocessable Entity | Request validation failed |
| 500 | Internal Server Error | Server-side error |

---

## Usage Examples

### Complete Workflow Example

#### Step 1: Create a Job
```bash
curl -X POST 'https://api.staging.brainsuite.ai/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/create' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "channel": "Facebook",
      "projectName": "Summer Campaign 2024",
      "assetLanguage": "en-US",
      "iconicColorScheme": "manufactory",
      "intendedMessages": [
        "natural ingredients",
        "healthy lifestyle"
      ],
      "intendedMessagesLanguage": "en-US",
      "brandValues": [
        "Naturalness",
        "Joy",
        "Innovation"
      ],
      "brandValuesLanguage": "en-US",
      "legs": [
        {
          "name": "Hero Image Variant A",
          "staticImage": {
            "assetId": "hero-img-001",
            "name": "hero_image_v1.jpg",
            "url": "https://example.com/assets/hero_image_v1.jpg",
            "assets": []
          }
        },
        {
          "name": "Product Shot Variant B",
          "staticImage": {
            "assetId": "product-img-001",
            "name": "product_shot_v1.jpg",
            "url": "https://example.com/assets/product_shot_v1.jpg",
            "assets": []
          }
        }
      ]
    }
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Step 2: Check Job Status
```bash
curl -X GET 'https://api.staging.brainsuite.ai/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/550e8400-e29b-41d4-a716-446655440000' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

#### Step 3: Get Results via Cockpit
```bash
curl -X GET 'https://api.staging.brainsuite.ai/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/cockpit' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

### Announce and Start Job Workflow
```bash
# Step 1: Announce Job
curl -X POST 'https://api.staging.brainsuite.ai/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/announce' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "channel": "Instagram",
      "projectName": "Spring Collection",
      "assetLanguage": "en-US",
      "intendedMessages": ["sustainable fashion"],
      "intendedMessagesLanguage": "en-US",
      "brandValues": ["Sustainability", "Quality"],
      "brandValuesLanguage": "en-US",
      "legs": [
        {
          "name": "Main Showcase",
          "staticImage": {
            "assetId": "main-001",
            "name": "showcase.jpg",
            "url": "https://example.com/assets/showcase.jpg",
            "assets": []
          }
        }
      ]
    }
  }'

# Step 2: Start the Job
curl -X POST 'https://api.staging.brainsuite.ai/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API/{jobId}/start' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

---

## Important Notes

### Asset Upload Considerations
1. **Upload URL Validity:** The uploadUrl expires after 5 minutes
2. **File Size Limit:** Maximum file size is 5GB
3. **Security:** Never share upload credentials with third parties
4. **Asset Matching:** Each asset announcement must match exactly one assetId
5. **Replacement Behavior:** If an assetId already exists, it will be replaced, not appended

### Default Values
When parameters are uncertain, use these defaults:
- `assetLanguage`: "en-US"
- `intendedMessagesLanguage`: "en-US"
- `brandValuesLanguage`: "en-US"
- `intendedMessages`: ["natural ingredients", "healthy"]
- `brandValues`: ["Naturalness", "Joy"]
- `iconicColorScheme`: "manufactory"

### Field Constraints
- `intendedMessages` items: Maximum 50 words each
- `brandValues` items: Maximum 50 words each
- `legs` array: Minimum 1 item, Maximum 10 items
- File format: Standard image and video formats

### Workflow Best Practices
1. **Create First:** Always use `/create` endpoint to initialize a job
2. **Announce Optional:** Use `/announce` for staged asset announcements
3. **Check Status:** Regularly poll `/jobId` to monitor progress
4. **Export Results:** Use `/cockpit` to aggregate and export all results

---

## API Status and Support

- **API Version:** 1.0.0
- **Last Updated:** 2024
- **Status:** Production Ready
- **Support:** Contact Brainsuite support team via the app interface

---

## Related APIs

- **ACE Social Media Video (Seb):** For video asset analysis
- **ACE eCom Feed Test:** For e-commerce feed analysis

---

## Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/create` | POST | Create a new analysis job |
| `/announce` | POST | Announce a new job |
| `/{jobId}/assets` | POST | Upload assets for a job |
| `/{jobId}/start` | POST | Start job processing |
| `/{jobId}` | GET | Get job status |
| `/cockpit` | GET | Export aggregated results |

---

*This documentation is auto-generated from the OpenAPI specification and provides a comprehensive guide for using the ACE Social Media Static API.*