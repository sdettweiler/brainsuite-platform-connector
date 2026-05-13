---
status: deferred
phase: 15-tiktok-asset-download
source: [15-VERIFICATION.md]
started: 2026-05-08T17:00:00Z
updated: 2026-05-08T17:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. TikTok video ad asset_url populated after real sync
expected: After triggering a TikTok sync for a connection with video ads, run: `SELECT asset_url FROM tiktok_raw_performance WHERE video_id IS NOT NULL LIMIT 5;` — all rows have a non-null MinIO/S3 URL ending in `.mp4`. Also confirm `SELECT asset_url FROM creative_assets WHERE platform='TIKTOK' AND asset_format='VIDEO' LIMIT 5;` returns non-null values.
result: [deferred — live TikTok sync required; carry to v1.4]

### 2. TikTok image-only ad asset_url populated after real sync
expected: After sync, run: `SELECT asset_url FROM tiktok_raw_performance WHERE video_id IS NULL AND image_ids IS NOT NULL LIMIT 5;` — all rows have a non-null MinIO/S3 URL ending in `.jpg`.
result: [deferred — live TikTok sync required; carry to v1.4]

### 3. Re-sync does not re-download already-present assets (S3 idempotency)
expected: Run a second sync for the same connection. MinIO access logs (or absence of `INFO Downloaded TikTok video/image` log lines) confirm no new uploads. Previously downloaded files are returned via `file_exists` early return.
result: [deferred — live TikTok sync required; carry to v1.4]

## Summary

total: 3
passed: 0
issues: 0
pending: 0
skipped: 3
blocked: 0

## Gaps
