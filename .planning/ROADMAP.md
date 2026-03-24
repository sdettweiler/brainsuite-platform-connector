# Roadmap: BrainSuite Platform Connector

## Overview

Starting from a brownfield Angular 17 + FastAPI application already syncing creatives from four ad platforms, this roadmap closes four gaps in sequence: first decouple the platform from Replit into a portable Docker Compose stack so the product can be deployed anywhere; then fix the production security vulnerabilities that block external user onboarding; then wire in the BrainSuite scoring pipeline — the primary milestone deliverable; finally polish the dashboard UX and surface sync reliability so agencies can trust the data they see.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure Portability** - Decouple from Replit; run locally and deploy on any cloud via Docker Compose (completed 2026-03-20)
- [x] **Phase 2: Security Hardening** - Fix production security blockers and code quality issues before external users onboard (completed 2026-03-23)
- [x] **Phase 3: BrainSuite Scoring Pipeline** - Wire the BrainSuite API into an async scoring pipeline and surface scores in the dashboard (completed 2026-03-24)
- [ ] **Phase 4: Dashboard Polish + Reliability** - Complete the creative performance UI and surface sync health to agencies

## Phase Details

### Phase 1: Infrastructure Portability
**Goal**: The application runs fully outside Replit — local dev via Docker Compose and deployable to any cloud provider via standard container tooling
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, INFRA-08
**Success Criteria** (what must be TRUE):
  1. Developer can run the full stack locally with a single `docker compose up` command with no Replit account or tooling required
  2. Application deploys and runs on a non-Replit cloud provider (e.g., Railway, Render, or bare VPS) using the standard container stack
  3. All Replit-specific sidecars (object storage, credential exchange) are replaced — removing Replit environment variables causes no runtime dependency failures
  4. A new developer can generate a valid `.env` from `.env.example` and the setup script without reading source code
  5. Redis runs as a peer Docker Compose service, not a Replit sidecar
**Plans:** 3/3 plans complete
Plans:
- [ ] 01-01-PLAN.md — Docker Compose services (Redis + MinIO), Replit code removal, .env.example update
- [ ] 01-02-PLAN.md — Replace ObjectStorageService with boto3 S3 implementation
- [ ] 01-03-PLAN.md — Interactive setup script and Makefile

### Phase 2: Security Hardening
**Goal**: All critical production security vulnerabilities are fixed and code quality is consistent enough for external users to safely onboard
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, QUAL-01, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. OAuth flow completes correctly when the FastAPI app runs on two workers simultaneously (no "session not found" errors)
  2. Browser developer tools show no JWT token in localStorage after login — token lives only in memory and an httpOnly cookie
  3. App refuses to start and logs a clear error if TOKEN_ENCRYPTION_KEY is missing or malformed
  4. Requesting a crafted asset path (e.g., `../../etc/passwd`) returns 400, not a file or 500
  5. All API endpoints return errors in a consistent JSON shape; frontend TypeScript has no `any` types for API response DTOs
**Plans:** 6/6 plans complete
Plans:
- [ ] 02-01-PLAN.md — Wave 0 test scaffolds + SEC-03/SEC-04/SEC-05/SEC-06 quick security fixes
- [ ] 02-02-PLAN.md — SEC-01 Redis OAuth session migration
- [ ] 02-03-PLAN.md — SEC-02 backend: httpOnly cookie refresh token migration
- [ ] 02-04-PLAN.md — SEC-02 frontend: Angular auth migration to in-memory token + cookie refresh
- [ ] 02-05-PLAN.md — QUAL-01 exception handling sweep (75 broad catches across 12 files)
- [ ] 02-06-PLAN.md — QUAL-02 frontend DTO typing + QUAL-03 error response consistency

### Phase 3: BrainSuite Scoring Pipeline
**Goal**: Every synced creative is automatically scored by the BrainSuite API and the score plus dimension breakdown is visible in the dashboard
**Depends on**: Phase 2
**Requirements**: SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05, SCORE-06, SCORE-07, SCORE-08
**Success Criteria** (what must be TRUE):
  1. After a platform sync completes, newly imported creatives appear with a scoring status indicator and receive a BrainSuite score within 15 minutes without any manual action
  2. Each creative in the dashboard displays a score badge; clicking the badge opens a dimension breakdown panel with all scoring dimensions returned by the BrainSuite API
  3. A user can trigger a manual re-score on any individual creative via the UI and see the score update after the next scheduler run
  4. BrainSuite API failures (429, 5xx) do not crash the scheduler or leave assets permanently stuck — failed assets retry automatically; 4xx failures mark the asset as permanently failed with a visible reason
  5. The frontend polling endpoint (`/scoring/status`) is only called while PENDING or PROCESSING assets are on screen — not on every page load
**Plans:** 6/6 plans complete
Plans:
- [x] 03-01-PLAN.md — DB model, migration, config, tenacity dep, test scaffolds
- [x] 03-02-PLAN.md — BrainSuiteScoreService (auth, create-job, poll, channel mapping)
- [x] 03-03-PLAN.md — Scoring batch job + harmonizer UNSCORED injection
- [x] 03-04-PLAN.md — Scoring API router + dashboard endpoint updates
- [x] 03-05-PLAN.md — Frontend score badge, polling, Creative Effectiveness tab
- [x] 03-06-PLAN.md — Seed BrainSuite MetadataField rows + setup.py/env updates

### Phase 4: Dashboard Polish + Reliability
**Goal**: Agencies can immediately identify top and bottom creative performers and trust that the data is current, with platform sync health visible at a glance
**Depends on**: Phase 3
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, REL-01, REL-02, REL-03
**Success Criteria** (what must be TRUE):
  1. Every creative in the list view shows a visible thumbnail (image preview or video frame) alongside its performance metrics and score badge
  2. User can sort the creative table by BrainSuite score, ROAS, CTR, and spend; can filter by platform, date range, and score range — sorted/filtered results update without page reload
  3. Platform connection panel shows last sync time and a health indicator (connected / token expired / sync failed) for each connected platform
  4. When a platform token expires or a sync fails, the user sees an inline reconnect prompt — no silent stale data
  5. APScheduler runs on exactly one worker regardless of how many app instances are deployed (SCHEDULER_ENABLED guard prevents duplicate job execution and double-counted metrics)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure Portability | 3/3 | Complete   | 2026-03-20 |
| 2. Security Hardening | 6/6 | Complete   | 2026-03-23 |
| 3. BrainSuite Scoring Pipeline | 6/6 | Complete   | 2026-03-24 |
| 4. Dashboard Polish + Reliability | 0/TBD | Not started | - |
