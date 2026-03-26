#!/usr/bin/env python3
"""BrainSuite Static API Discovery Spike

Confirms: ACE_STATIC_SOCIAL_STATIC_API endpoint reachability, auth with existing
BRAINSUITE_CLIENT_ID / BRAINSUITE_CLIENT_SECRET credentials, announce→upload→start
flow, and documents the full response shape for image scoring implementation.

Usage:
    BRAINSUITE_CLIENT_ID=xxx BRAINSUITE_CLIENT_SECRET=yyy python scripts/spike_static_api.py

Output:
    Prints step-by-step status to stdout.
    On success/failure: dumps full response JSON to docs/spike_static_response.json
"""
import base64
import json
import os
import sys
import time
from io import BytesIO

# ---------------------------------------------------------------------------
# Minimal JPEG (1x1 red pixel) created inline — no external file needed
# ---------------------------------------------------------------------------
MINIMAL_JPEG_BYTES = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
    0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
    0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
    0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
    0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
    0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
    0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
    0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
    0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD4, 0xFF, 0xD9
])

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    import requests as _requests_check  # noqa: F401
except ImportError:
    pass


def get_credentials():
    """Read credentials from environment variables."""
    client_id = os.environ.get("BRAINSUITE_CLIENT_ID")
    client_secret = os.environ.get("BRAINSUITE_CLIENT_SECRET")

    if not client_id or not client_secret:
        # Try loading from .env in the backend directory
        env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("BRAINSUITE_CLIENT_ID=") and not client_id:
                        client_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("BRAINSUITE_CLIENT_SECRET=") and not client_secret:
                        client_secret = line.split("=", 1)[1].strip().strip('"').strip("'")

    return client_id, client_secret


def step(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")


def main():
    import httpx as httpx_module
    import json as json_module

    AUTH_URL = "https://auth.brainsuite.ai/oauth2/token"
    BASE_URL = "https://api.brainsuite.ai"
    STATIC_BASE = f"{BASE_URL}/v1/jobs/ACE_STATIC/ACE_STATIC_SOCIAL_STATIC_API"

    client_id, client_secret = get_credentials()

    if not client_id or not client_secret:
        print("ERROR: BRAINSUITE_CLIENT_ID and BRAINSUITE_CLIENT_SECRET must be set.")
        print("Set them as environment variables or add them to backend/.env")
        print("")
        print("Script is ready to run when credentials are available.")
        print("SPIKE RESULT: CREDENTIALS NOT AVAILABLE IN DEV ENVIRONMENT")
        sys.exit(2)

    # -------------------------------------------------------------------------
    # Step 1: Auth
    # -------------------------------------------------------------------------
    step("Step 1: Authenticate")
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()

    with httpx_module.Client(timeout=30) as client:
        auth_resp = client.post(
            AUTH_URL,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )

    print(f"Auth HTTP status: {auth_resp.status_code}")
    if auth_resp.status_code != 200:
        print(f"Auth FAILED: {auth_resp.text[:500]}")
        print("SPIKE RESULT: AUTH FAILED")
        sys.exit(1)

    auth_data = auth_resp.json()
    token = auth_data["access_token"]
    token_type = auth_data.get("token_type", "Bearer")
    print(f"Auth: SUCCESS — token_type={token_type} token_prefix={token[:20]}...")
    print("PROD-01: BrainSuite credentials authenticate against Static endpoint — CONFIRMED")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # -------------------------------------------------------------------------
    # Step 2: Announce job
    # -------------------------------------------------------------------------
    step("Step 2: Announce job (POST /announce)")
    announce_payload = {
        "input": {
            "channel": "Facebook",
            "projectName": "Discovery Spike",
            "assetLanguage": "en-US",
            "iconicColorScheme": "manufactory",
            "legs": [{
                "name": "test-image.jpg",
                "staticImage": {
                    "assetId": "leg1",
                    "name": "test-image.jpg"
                }
            }]
        }
    }

    with httpx_module.Client(timeout=30) as client:
        announce_resp = client.post(
            f"{STATIC_BASE}/announce",
            headers=headers,
            json=announce_payload,
        )

    print(f"Announce HTTP status: {announce_resp.status_code}")
    print(f"Announce response body: {announce_resp.text[:500]}")
    if announce_resp.status_code not in (200, 201, 202):
        print("Announce FAILED")
        sys.exit(1)

    announce_data = announce_resp.json()
    job_id = announce_data.get("id") or announce_data.get("jobId")
    if not job_id:
        print(f"ERROR: no job ID in announce response: {announce_data}")
        sys.exit(1)

    print(f"Announce: SUCCESS — job_id={job_id}")

    # -------------------------------------------------------------------------
    # Step 3: Announce asset (get presigned upload URL)
    # -------------------------------------------------------------------------
    step(f"Step 3: Announce asset (POST /{job_id}/assets)")
    asset_payload = {"assetId": "leg1", "name": "test-image.jpg"}

    with httpx_module.Client(timeout=30) as client:
        asset_resp = client.post(
            f"{STATIC_BASE}/{job_id}/assets",
            headers=headers,
            json=asset_payload,
        )

    print(f"Asset announce HTTP status: {asset_resp.status_code}")
    print(f"Asset announce response: {asset_resp.text[:500]}")
    if asset_resp.status_code not in (200, 201, 202):
        print("Asset announce FAILED")
        sys.exit(1)

    asset_data = asset_resp.json()
    upload_url = asset_data.get("uploadUrl")
    s3_fields = asset_data.get("fields", {})
    print(f"Asset announce: SUCCESS — uploadUrl present={bool(upload_url)}")
    if not upload_url:
        print(f"ERROR: no uploadUrl in asset announce response: {asset_data}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Step 4: Upload image to presigned S3 URL
    # -------------------------------------------------------------------------
    step("Step 4: Upload 1x1 JPEG to presigned S3 URL")
    form_data = {k: (None, v) for k, v in s3_fields.items()}
    form_data["file"] = ("test-image.jpg", MINIMAL_JPEG_BYTES, "image/jpeg")

    with httpx_module.Client(timeout=120) as client:
        upload_resp = client.post(upload_url, files=form_data)

    print(f"Upload HTTP status: {upload_resp.status_code}")
    if upload_resp.status_code not in (200, 204):
        print(f"Upload FAILED: {upload_resp.text[:300]}")
        sys.exit(1)
    print("Upload: SUCCESS")

    # -------------------------------------------------------------------------
    # Step 5: Start job (empty body — briefing data is in announce for Static)
    # -------------------------------------------------------------------------
    step(f"Step 5: Start job (POST /{job_id}/start)")
    with httpx_module.Client(timeout=30) as client:
        start_resp = client.post(
            f"{STATIC_BASE}/{job_id}/start",
            headers=headers,
            json={},
        )

    print(f"Start HTTP status: {start_resp.status_code}")
    print(f"Start response: {start_resp.text[:500]}")
    if start_resp.status_code not in (200, 201, 202):
        print("Start FAILED")
        sys.exit(1)
    print("Start: SUCCESS")

    # Capture rate limit headers
    rate_limit_headers = {
        "x-ratelimit-limit": start_resp.headers.get("x-ratelimit-limit"),
        "x-ratelimit-used": start_resp.headers.get("x-ratelimit-used"),
        "x-ratelimit-reset": start_resp.headers.get("x-ratelimit-reset"),
        "x-ratelimit-resource": start_resp.headers.get("x-ratelimit-resource"),
    }
    print(f"Rate limit headers: {rate_limit_headers}")

    # -------------------------------------------------------------------------
    # Step 6: Poll until terminal status
    # -------------------------------------------------------------------------
    step(f"Step 6: Poll job status (GET /{job_id})")
    terminal_statuses = {"Succeeded", "Failed", "Stale"}
    in_progress = {"Announced", "Scheduled", "Created", "Started"}
    max_polls = 60
    poll_interval = 30

    final_data = None
    for poll_num in range(max_polls):
        with httpx_module.Client(timeout=30) as client:
            poll_resp = client.get(
                f"{STATIC_BASE}/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if poll_resp.status_code == 401:
            print("Poll 401 — token expired, re-authenticating...")
            break

        poll_resp.raise_for_status()
        poll_data = poll_resp.json()
        status = poll_data.get("status", "")
        print(f"Poll {poll_num + 1}/{max_polls}: status={status}")

        if status in terminal_statuses:
            final_data = poll_data
            break

        if status in in_progress:
            time.sleep(poll_interval)
            continue

        print(f"Unexpected status: {status}")
        time.sleep(poll_interval)
    else:
        print("ERROR: Polling timed out")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Step 7: Output results
    # -------------------------------------------------------------------------
    step("Step 7: Results")
    if final_data is None:
        print("SPIKE RESULT: POLLING INCOMPLETE")
        sys.exit(1)

    status = final_data.get("status")
    print(f"Final status: {status}")
    print(f"\nFull response JSON:\n{json_module.dumps(final_data, indent=2)}")

    # Save to docs/spike_static_response.json
    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "spike_static_response.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json_module.dump(final_data, f, indent=2)
    print(f"\nFull response saved to: {output_path}")

    if status == "Succeeded":
        output = final_data.get("output", {})
        leg_results = output.get("legResults", [])
        has_leg_results = bool(leg_results)
        has_executive_summary = has_leg_results and "executiveSummary" in leg_results[0]
        print(f"\nResponse shape analysis:")
        print(f"  output.legResults present: {has_leg_results}")
        print(f"  output.legResults[0].executiveSummary present: {has_executive_summary}")
        if has_executive_summary:
            summary = leg_results[0]["executiveSummary"]
            print(f"  executiveSummary keys: {list(summary.keys())}")
        print(f"\nRate limit headers observed: {rate_limit_headers}")
        print(f"\nSPIKE RESULT: SUCCESS — Static API confirmed working with existing credentials")
    else:
        print(f"\nSPIKE RESULT: Job ended with status={status}")
        error = final_data.get("errorDetail") or final_data.get("error", "")
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
