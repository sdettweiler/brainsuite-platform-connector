---
status: complete
phase: 05-brainsuite-image-scoring
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md]
started: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Clear ephemeral state. Start the application from scratch (docker-compose up or uvicorn). Alembic migrations run without errors (including the new endpoint_type and image metadata seed migrations). The backend health check or a basic API call returns live data.
result: pass

### 2. ScoringEndpointType routing
expected: Run `python -c "from app.services.scoring_endpoint_type import get_endpoint_type; print(get_endpoint_type('META','IMAGE'), get_endpoint_type('TIKTOK','IMAGE'), get_endpoint_type('META','VIDEO'))"` from the backend directory. Output should be `STATIC_IMAGE UNSUPPORTED VIDEO` — Meta images route to STATIC_IMAGE, non-Meta images to UNSUPPORTED, and videos stay VIDEO.
result: pass

### 3. Alembic migration — endpoint_type column
expected: After running `alembic upgrade head`, querying `SELECT endpoint_type FROM creative_score_results LIMIT 5` returns rows (no "column does not exist" error). Existing video rows show `endpoint_type = 'VIDEO'` (backfilled by migration).
result: pass

### 4. Harmonizer creates image score rows at sync
expected: After a sync run for a Meta ad account that has image creatives, the `creative_score_results` table contains rows for those image assets with `endpoint_type = 'STATIC_IMAGE'` and `scoring_status = 'UNSCORED'`. Non-Meta image assets (e.g. TikTok) get `endpoint_type = 'UNSUPPORTED'` and `scoring_status = 'UNSUPPORTED'`.
result: pass

### 5. Rescore returns 422 for UNSUPPORTED assets
expected: Calling `POST /api/v1/scoring/rescore/{asset_id}` for an asset with `scoring_status = 'UNSUPPORTED'` returns HTTP 422 (not 200 or 400). The response body should indicate the asset is unsupported for scoring.
result: skipped
reason: No non-Meta image assets (UNSUPPORTED) in DB at time of testing

### 6. Dashboard UNSUPPORTED badge
expected: In the dashboard grid, an image creative with `scoring_status = 'UNSUPPORTED'` shows a grey dash overlay (no coloured ACE score number). Hovering over the dash shows a tooltip with text like "Image scoring not supported for this platform".
result: pass

### 7. CE tab UNSUPPORTED notice
expected: Opening the asset detail dialog for an UNSUPPORTED image creative and clicking the Creative Effectiveness tab shows a notice block (not the normal CE dimension breakdown). The notice explains scoring is not supported for this asset type/platform.
result: skipped
reason: No UNSUPPORTED assets in DB at time of testing

### 8. CE tab normal display for scored assets
expected: Opening the asset detail dialog for a video asset (or a scored image asset) shows the normal CE tab — the dimension breakdown grid renders correctly with no UNSUPPORTED notice visible.
result: pass

### 9. Image-only metadata display
expected: In the asset detail dialog CE tab for an IMAGE asset, an "Intended Messages" and "Iconic Color Scheme" metadata section is visible. For a VIDEO asset, these fields are NOT shown (the section is absent entirely).
result: issue
reported: "Not seeing image metadata fields (Intended Messages / Iconic Color Scheme) for image assets in the CE tab"
severity: major

### 10. Image metadata fields seeded in DB
expected: After applying migrations, the `metadata_fields` table contains rows for `brainsuite_intended_messages` (type TEXT, sort_order 8) and `brainsuite_iconic_color_scheme` (type SELECT with default "manufactory", sort_order 9) — one pair per organization.
result: pass

## Summary

total: 10
passed: 6
issues: 1
pending: 0
skipped: 3

## Gaps

- truth: "CE tab for an IMAGE asset shows Intended Messages and Iconic Color Scheme metadata fields; VIDEO assets do not show them"
  status: failed
  reason: "User reported: Not seeing image metadata fields for image assets in the CE tab. Diagnosis: imageMetadataFields getter and image-only metadata section were not added to asset-detail-dialog.component.ts — the commit only changed 7 lines (interface field renames). UNSUPPORTED CE tab notice also missing from dialog."
  severity: major
  test: 9
  artifacts: [frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts]
  missing: [imageMetadataFields getter, image-only metadata section in CE preview column, UNSUPPORTED notice block in CE tab]
