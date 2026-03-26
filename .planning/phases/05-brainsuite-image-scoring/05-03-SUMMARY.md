---
phase: 05-brainsuite-image-scoring
plan: 03
subsystem: ui
tags: [angular, dashboard, brainsuite, scoring, metadata, alembic, migration]

requires:
  - phase: 05-02
    provides: "BrainSuiteStaticScoreService, UNSUPPORTED scoring_status value, endpoint_type routing, scheduler branching"
  - phase: 05-01
    provides: "ScoringEndpointType enum, endpoint_type migration, BRAINSUITE_API.md with iconicColorScheme confirmed values"

provides:
  - "Dashboard grid UNSUPPORTED badge: grey dash + tooltip 'Image scoring not supported for this platform' via ngSwitchCase"
  - "Asset detail dialog CE tab: explicit UNSUPPORTED notice block when scoring_status=UNSUPPORTED"
  - "imageMetadataFields getter: reads brainsuite_intended_messages/brainsuite_iconic_color_scheme from metadata_values, only for IMAGE assets"
  - "Alembic migration m4n5o6p7q8r9: seeds brainsuite_intended_messages (TEXT) and brainsuite_iconic_color_scheme (SELECT, default=manufactory) per org"

affects:
  - "Human verification: complete Phase 5 end-to-end visual check"

tech-stack:
  added: []
  patterns:
    - "ngSwitch on scoring_status in dashboard tile: UNSUPPORTED case returns overlay-ace-dash before ngSwitchDefault numeric badge"
    - "CE tab guard: *ngIf on scoring_status !== 'UNSUPPORTED' wraps full ce-layout to show unsupported-notice instead"
    - "imageMetadataFields getter: reads from asset.metadata_values map keyed by field name; returns empty array for non-IMAGE assets"

key-files:
  created:
    - backend/alembic/versions/m4n5o6p7q8r9_seed_image_metadata_fields.py
  modified:
    - frontend/src/app/features/dashboard/dashboard.component.ts
    - frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts

key-decisions:
  - "Used ngSwitch on scoring_status in dashboard tile (replacing the single overlay-ace div) so UNSUPPORTED is handled explicitly, not via getAceClass fallback"
  - "CE tab UNSUPPORTED guard: rendered as full-width notice outside ce-layout grid so it fills the tab area rather than overlapping the two-column layout"
  - "imageMetadataFields reads from asset.metadata_values (field-name-keyed map) — matches existing backend API response pattern"
  - "Only 'manufactory' seeded as iconicColorScheme value — additional values pending live spike confirmation per BRAINSUITE_API.md"

patterns-established:
  - "scoring_status UNSUPPORTED case: always render grey dash overlay + tooltip in tile; render notice block in CE tab"
  - "Image-only metadata: filtered via asset_format=IMAGE guard in TypeScript getter, not in template loop"

requirements-completed: [IMG-04]

duration: 8min
completed: 2026-03-26
status: AWAITING_CHECKPOINT
---

# Phase 05 Plan 03: Image Scoring UI Summary

**Angular dashboard UNSUPPORTED badge (grey dash + tooltip), asset detail CE tab UNSUPPORTED notice, image-only metadata display (Intended Messages / Iconic Color Scheme), and Alembic migration seeding two new MetadataField rows per org**

> NOTE: This plan reached checkpoint:human-verify after Task 1. Human verification pending.

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-26T09:12:00Z
- **Completed (auto tasks):** 2026-03-26T09:18:00Z
- **Tasks completed:** 1 of 2 (Task 2 is checkpoint:human-verify)
- **Files modified:** 3

## Accomplishments

- Angular production build passes with all three file changes
- Dashboard tile now shows grey dash with tooltip for UNSUPPORTED assets, score number for all other statuses
- Asset detail dialog CE tab now guards against UNSUPPORTED status with an informative notice
- Image-only metadata (Intended Messages, Iconic Color Scheme) visible in CE tab only when asset_format=IMAGE
- Alembic migration seeds brainsuite_intended_messages (TEXT, sort_order=8) and brainsuite_iconic_color_scheme (SELECT, default=manufactory, sort_order=9) per organization, with one MetadataFieldValue row for "manufactory"

## Task Commits

1. **Task 1: Seed image metadata fields + frontend UNSUPPORTED badge + image-only metadata display** - `7ae97f4` (feat)

## Files Created/Modified

- `backend/alembic/versions/m4n5o6p7q8r9_seed_image_metadata_fields.py` - Seeds brainsuite_intended_messages and brainsuite_iconic_color_scheme MetadataField rows per org; single MetadataFieldValue row for manufactory
- `frontend/src/app/features/dashboard/dashboard.component.ts` - Added ngSwitch on scoring_status in tile overlay: UNSUPPORTED renders grey dash + matTooltip; ngSwitchDefault renders existing numeric badge; added overlay-ace-dash CSS class
- `frontend/src/app/features/dashboard/dialogs/asset-detail-dialog.component.ts` - Added unsupported-notice block in CE tab, ce-layout wrapped in *ngIf scoring_status !== UNSUPPORTED, imageMetadataFields getter, image-only metadata section in CE preview column

## Decisions Made

- ngSwitch on scoring_status wraps the existing overlay-ace div so UNSUPPORTED gets its own case before the default numeric badge — cleaner than a nested *ngIf inside getAceClass
- UNSUPPORTED notice placed before the ce-layout grid so it displays as a full-width banner, not within the two-column layout
- imageMetadataFields reads from `asset.metadata_values` (field-name-keyed map) — assumes backend API returns metadata_values on asset detail response; if key is absent field is not shown (graceful degradation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added ngSwitchDefault wrapper around existing score badge**
- **Found during:** Task 1 (Part B — dashboard badge)
- **Issue:** The plan described adding a new `*ngSwitchCase` for UNSUPPORTED in an existing ngSwitch, but the dashboard template had no ngSwitch — just a single `overlay-ace` div. Needed to add both the ngSwitch container and wrap the existing badge as ngSwitchDefault.
- **Fix:** Replaced single `overlay-ace` div with `[ngSwitch]="asset.scoring_status"` container holding UNSUPPORTED case and ngSwitchDefault (existing badge).
- **Files modified:** frontend/src/app/features/dashboard/dashboard.component.ts
- **Verification:** Angular production build passes; both cases present
- **Committed in:** 7ae97f4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — adapted to actual template structure)
**Impact on plan:** Deviation required to implement the planned behavior — template had no existing ngSwitch to add a case to. Fix achieves identical visual result as planned.

## Issues Encountered

None beyond the ngSwitch structure adaptation above.

## Known Stubs

- `imageMetadataFields` getter reads from `asset?.metadata_values` which may not exist in the API response yet (depends on backend asset detail endpoint returning metadata_values). Field is shown only when key exists — graceful degradation if not present. This will be wired when the asset detail endpoint is updated to return metadata_values map.

## Next Phase Readiness

- Phase 5 implementation complete pending human verification (Task 2 checkpoint)
- BrainSuite credentials (PROD-01) still needed to run live scoring in production
- Google Ads OAuth consent screen (PROD-02) still needs manual verification

---
*Phase: 05-brainsuite-image-scoring*
*Completed (auto tasks): 2026-03-26*
