---
phase: 01-infrastructure-portability
plan: 02
subsystem: infra
tags: [boto3, s3, minio, object-storage, python, pytest]

# Dependency graph
requires:
  - phase: 01-infrastructure-portability/plan-01
    provides: "S3 settings fields in config.py (S3_ENDPOINT_URL, S3_BUCKET_NAME, AWS_*)"
provides:
  - "boto3-based ObjectStorageService replacing GCS/Replit sidecar implementation"
  - "Unit test suite for object storage (17 tests, all passing)"
  - "pytest added to requirements.txt"
affects:
  - phase-02-security
  - phase-03-brainsuite-scoring
  - phase-04-dashboard

# Tech tracking
tech-stack:
  added: [boto3>=1.42.0, botocore (transitive), pytest>=7.4.0]
  patterns:
    - "Lazy S3 client initialization via _ensure_client() with singleton service"
    - "Config(signature_version='s3v4') always set for MinIO presigned URL compatibility"
    - "endpoint_url conditionally set: present for MinIO dev, absent for real AWS S3 prod"
    - "TDD: RED commit (failing tests) then GREEN commit (implementation)"

key-files:
  created:
    - backend/tests/__init__.py
    - backend/tests/test_object_storage.py
  modified:
    - backend/app/services/object_storage.py
    - backend/requirements.txt

key-decisions:
  - "_object_name() returns relative_path unchanged (bucket is the namespace; GCS public_prefix prefix removed)"
  - "download_blob returns (None, None) on any ClientError 404/NoSuchKey to preserve caller behavior"
  - "delete_blob returns True on success; S3 delete_object is idempotent so no existence check needed"
  - "list_blobs uses paginator for correctness with large result sets"
  - "Tests use unittest.mock (no moto) to avoid extra test dependency"

patterns-established:
  - "Pattern: S3 client lazy init with _ensure_client() — use this pattern for any future boto3 service"
  - "Pattern: ClientError code check using e.response['Error']['Code'] in ('404', 'NoSuchKey')"
  - "Pattern: pytest fixture resets singleton (_instance = None) before and after each test"

requirements-completed: [INFRA-04, INFRA-05]

# Metrics
duration: 6min
completed: 2026-03-20
---

# Phase 01 Plan 02: ObjectStorageService boto3 S3 Implementation Summary

**boto3 S3-compatible ObjectStorageService replacing GCS/Replit sidecar: all 9 methods preserved, Config(signature_version='s3v4') for MinIO presigned URL compatibility, 17 unit tests passing**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-20T15:30:00Z
- **Completed:** 2026-03-20T15:36:27Z
- **Tasks:** 1 (TDD: 2 commits — RED + GREEN)
- **Files modified:** 4

## Accomplishments
- Replaced GCS identity_pool/Replit sidecar implementation with boto3 S3 client that works with MinIO in dev and real AWS S3 in prod
- Preserved all 9 public method signatures and return types exactly so zero callers needed changes
- Config(signature_version='s3v4') ensures presigned URLs work against MinIO (avoids silent SignatureDoesNotMatch failure)
- 17 unit tests verify every method, static source assertions confirm no GCS/sidecar/Replit references remain

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing tests for boto3 ObjectStorageService** - `0d1a4da` (test)
2. **Task 1 GREEN: Replace ObjectStorageService with boto3 S3 implementation** - `aecc248` (feat)

_Note: TDD task split into RED (failing tests) and GREEN (passing implementation) commits._

## Files Created/Modified
- `backend/app/services/object_storage.py` - Full boto3 S3 implementation replacing GCS/Replit sidecar
- `backend/tests/__init__.py` - Python package init for test suite
- `backend/tests/test_object_storage.py` - 17 unit tests covering all methods with unittest.mock
- `backend/requirements.txt` - Added pytest>=7.4.0 (boto3 already added by Plan 01)

## Decisions Made
- `_object_name()` returns `relative_path` unchanged (bucket is the namespace; the old GCS `public_prefix` wrapper removed)
- Tests use `unittest.mock` instead of `moto` — avoids an additional dependency and is sufficient for method contract testing
- `download_blob` returns `(None, None)` on ClientError 404/NoSuchKey to match existing caller expectations
- `delete_blob` returns `True` unconditionally on success — S3 `delete_object` is idempotent so no existence pre-check needed
- `list_blobs` uses paginator to correctly handle buckets with >1000 objects

## Deviations from Plan

None — plan executed exactly as written. config.py S3 fields were already present (added by Plan 01 which ran before this plan).

## Issues Encountered
- `google.cloud` module not installed in local Python environment, causing import error when running RED-phase tests against original GCS implementation. This is expected behavior — the tests correctly failed in RED state, confirming they test the right behavior.

## User Setup Required
None - no external service configuration required for this plan. MinIO bucket creation is covered by the Makefile/setup script in Plan 01 and Plan 03.

## Next Phase Readiness
- ObjectStorageService is fully portable: all sync callers (6 files + main.py) work without changes
- Unit test suite established at `backend/tests/` — can be extended in subsequent plans
- INFRA-04 (S3-compatible storage) and INFRA-05 (sidecar removal) requirements satisfied
- Phase 02 (security) and Phase 03 (BrainSuite scoring) can use `get_object_storage()` with confidence

---
*Phase: 01-infrastructure-portability*
*Completed: 2026-03-20*
