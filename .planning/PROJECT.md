# BrainSuite Platform Connector

## What This Is

A production-ready multi-tenant SaaS platform that connects Meta, TikTok, Google Ads, and DV360 ad accounts, syncs creative assets and performance metrics into a unified dashboard, and automatically scores every imported creative for effectiveness via the BrainSuite API. Agencies use it to immediately identify which creatives to scale or kill based on objective effectiveness scores alongside ROAS, CTR, and spend.

## Core Value

A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## Current State

**Version:** v1.0 (shipped 2026-03-25)

**Stack:** Angular 17 + FastAPI + PostgreSQL + Redis + MinIO — fully containerized via Docker Compose
**Deployment:** Any cloud host or local dev via `docker compose up`
**LOC:** ~52,000 lines added across 276 files in v1.0 milestone

**What works:**
- Multi-tenant organization with RBAC
- OAuth connection + background sync for Meta, TikTok, Google Ads, DV360
- Creative asset storage via S3-compatible storage (MinIO local / S3 production)
- Automatic BrainSuite scoring pipeline (15-min scheduler, UNSCORED→COMPLETE state machine, tenacity retry)
- Dashboard: score badge, Creative Effectiveness dimension tab, sort/filter by score/ROAS/CTR/spend, score range slider
- Platform health monitoring: sync time, health badges, reconnect prompts
- Production security: httpOnly cookie auth, Redis OAuth sessions, typed DTOs

**Known gaps / tech debt:**
- BrainSuite scoring credentials need to be configured in production (code path fully implemented)
- Google Ads OAuth consent screen "Published" status should be verified before external user onboarding

## Requirements

### Validated

- ✓ User authentication (register, login, JWT session management) — existing
- ✓ Multi-tenant organization structure with RBAC — existing
- ✓ Meta OAuth connection and background sync — existing
- ✓ TikTok OAuth connection and background sync — existing
- ✓ Google Ads OAuth connection and background sync — existing
- ✓ DV360 OAuth connection and background sync — existing
- ✓ Creative asset storage (images, videos) via S3-compatible storage — v1.0 (Phase 1)
- ✓ Data harmonization layer (normalized metrics across platforms) — existing
- ✓ Unified dashboard with performance metrics — existing + v1.0
- ✓ Currency conversion across platforms — existing
- ✓ Docker Compose portability — zero Replit dependency — v1.0 (Phase 1)
- ✓ Production security hardening — httpOnly cookie auth, encrypted tokens, path traversal fix — v1.0 (Phase 2)
- ✓ BrainSuite API integration — POST asset + metadata, receive score + dimensions, store results — v1.0 (Phase 3)
- ✓ Creative scoring visible in dashboard — score badge, CE dimension tab, sort/filter by score range — v1.0 (Phase 3–4)
- ✓ Platform data reliability — health badges, reconnect prompts, token_expiry exposed, SCHEDULER_ENABLED guard — v1.0 (Phase 3–4)
- ✓ Dashboard UX polish — thumbnail fallback, score range slider, nullslast sort — v1.0 (Phase 4)

### Active

*(All v1.0 requirements validated — define v1.1 requirements via `/gsd:new-milestone`)*

### Out of Scope

- Real-time notifications — not requested, defer to v2
- Mobile app — web-first
- Audience/targeting asset import — user specified images and video only
- Ad copy / text creative scoring — not in scope for v1
- Creative identity across platforms — deferred to v2
- Replit deployment — replaced by portable Docker Compose

## Constraints

- **Deployment**: Docker Compose on any host — fully portable (Redis, MinIO, Postgres, backend, frontend)
- **Auth**: BrainSuite API accepts asset URL + metadata — schema confirmed via API discovery spike in Phase 3
- **Storage**: Assets in S3-compatible storage — BrainSuite integration references presigned URLs per request
- **Audience**: Internal-first, then client-facing — production hardening complete

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Angular 17 + FastAPI stack | Already built — brownfield project | ✓ Good |
| S3-compatible storage (MinIO/boto3) | Replaced Replit GCS sidecar — portable | ✓ Good |
| MinIO pinned to RELEASE.2025-10-15T17-29-55Z | Last official tag before maintenance mode | ✓ Good |
| httpOnly cookie for refresh token | XSS prevention — token never in localStorage | ✓ Good |
| Redis OAuth sessions (replace in-memory dict) | Survives multi-worker restarts | ✓ Good |
| Session-per-operation for BrainSuite scoring | Never hold DB session during HTTP calls | ✓ Good |
| on_conflict_do_nothing for UNSCORED injection | Prevents re-sync resetting completed scores | ✓ Good |
| SCHEDULER_ENABLED env var guard | Multi-worker Autoscale / cloud deployments — prevents duplicate job execution | ✓ Good |
| ngx-slider pinned to 17.0.2 | Angular 17 compatible; latest v21 requires Angular 21 | ✓ Good |
| Image + video only (not copy/audiences) | User scoped to creative assets only | ✓ Good |
| Score + dimensions (not just score) | User confirmed this is what BrainSuite returns | ✓ Validated in Phase 3 |

---
*Last updated: 2026-03-25 after v1.0 milestone*
