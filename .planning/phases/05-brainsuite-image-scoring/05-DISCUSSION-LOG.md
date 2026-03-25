# Phase 5: BrainSuite Image Scoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-25
**Phase:** 05-brainsuite-image-scoring
**Areas discussed:** Image API workflow, Unsupported platform handling, Image-specific metadata fields, Credentials architecture

---

## Image API Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Create-Job (URL-based) | Send MinIO presigned URL in legs[].staticImage.url — simpler, no file upload | |
| Announce→Upload→Start (same as video) | Download from MinIO, POST bytes to BrainSuite uploadUrl, then start — consistent with video | ✓ |
| You decide | Claude picks based on simplicity and Static API docs | |

**User's choice:** Announce→Upload→Start (same as video)
**Notes:** Consistency with established video pattern was the deciding factor even though Create-Job would be simpler.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — one leg per job | Each image asset gets its own Static job, same as video's one-asset-per-job | ✓ |
| Batch multiple images per job | Up to 10 legs per job for throughput, but complicates error handling | |

**User's choice:** One leg per job
**Notes:** Confirmed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Separate class | BrainSuiteStaticScoreService alongside existing BrainSuiteScoreService | ✓ |
| Extend existing class | Add image methods to BrainSuiteScoreService | |

**User's choice:** Separate class
**Notes:** Clean separation for different endpoints, payload shapes, and potential future divergence.

---

**Additional context provided by user:**
Areas of Interest (AOI) — undocumented Static API feature. Phase 5: do NOT submit. v1.2: (1) LLM Vision auto-detection of AOIs, (2) UI for editing/drawing bounding boxes. Supported AOI labels: brand-logo, flexible-3 (Product), flexible-4 (Key Message), flexible-2 (Call-to-Action), default (Other).

---

## Unsupported Platform Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Skip — leave UNSCORED forever | TikTok/Google/DV360 images never get a score entry | |
| Use Facebook as fallback | Score all non-Meta images with channel='Facebook' | |
| Separate UNSUPPORTED status | New scoring_status value so users can see why there's no score | ✓ |

**User's choice:** Separate UNSUPPORTED status
**Notes:** User wants transparency — agencies should understand why a creative has no score vs. it being unscored or failed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Grey dash with tooltip | Same visual as UNSCORED + info tooltip "Image scoring not supported for this platform" | ✓ |
| Distinct 'N/A' chip | Small grey 'N/A' chip to distinguish from "not scored yet" | |

**User's choice:** Grey dash with tooltip
**Notes:** Minimal UI change; tooltip provides context on hover.

---

## Image-Specific Metadata Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Use defaults, skip for now | iconicColorScheme defaults to 'manufactory', intendedMessages/brandValues omitted | |
| Add as new metadata fields | Seed new MetadataField rows for agencies to fill in | ✓ |

**User's choice:** Add as new metadata fields
**Notes:** User wants agencies to be able to provide these inputs.

---

| Option | Description | Selected |
|--------|-------------|----------|
| intendedMessages (array) | Multi-line textarea, one message per line, max 50 words each | ✓ |
| brandValues (array) | Same textarea pattern | |
| iconicColorScheme (select) | Color scheme SELECT — valid values need discovery spike | ✓ |

**User's choice:** intendedMessages + iconicColorScheme (brandValues excluded)
**Notes:** brandValues not added in Phase 5 — field is optional and omitted from payload.

---

## Credentials Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| BRAINSUITE_IMAGE_CLIENT_ID/_SECRET | Explicit image app naming | |
| BRAINSUITE_STATIC_CLIENT_ID/_SECRET | 'Static' matches API name | |
| Same credentials as video | Single client ID/secret works for both endpoints | ✓ |

**User's choice:** Same credentials for both video and image apps
**Notes:** User confirmed client ID and secret are shared across both BrainSuite app types. No new env vars needed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Verify existing creds hit Static endpoint | Confirm auth success during discovery spike; document in BRAINSUITE_API.md | ✓ |
| Update .env.example + Docker docs | Ensure docs don't imply separate credentials | |

**User's choice:** Verify existing creds hit Static endpoint
**Notes:** Verification during IMG-01 discovery spike is the PROD-01 deliverable.

---

## Claude's Discretion

- Static API job polling interval and timeout
- Token caching strategy for BrainSuiteStaticScoreService
- Exact iconicColorScheme valid enum values (from discovery spike)
- intendedMessages UI widget type (textarea vs. tag-input)
- Exact file location for ScoringEndpointType enum + lookup table

## Deferred Ideas

- AOI (Areas of Interest) — v1.2: LLM Vision auto-detection + bounding box UI editor
- brandValues metadata field — optional, omitted from Phase 5 payload, can add later
