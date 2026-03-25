# BrainSuite Platform Connector

## What This Is

A multi-tenant SaaS platform that allows users (agencies and advertisers) to connect their Meta, TikTok, Google Ads, and DV360 ad accounts, sync creative assets and performance metrics into a unified dashboard, and automatically score imported creatives for effectiveness via the BrainSuite API. Users come to quickly review creative performance and identify top/bottom performers across platforms.

## Core Value

A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## Requirements

### Validated

- ✓ User authentication (register, login, JWT session management) — existing
- ✓ Multi-tenant organization structure with RBAC — existing
- ✓ Meta OAuth connection and background sync — existing
- ✓ TikTok OAuth connection and background sync — existing
- ✓ Google Ads OAuth connection and background sync — existing
- ✓ DV360 OAuth connection and background sync — existing
- ✓ Creative asset storage (images, videos) via Google Cloud Storage — existing (migrated to boto3/S3-compatible in Phase 01)
- ✓ Data harmonization layer (normalized metrics across platforms) — existing
- ✓ Unified dashboard with performance metrics — existing (mostly working)
- ✓ Currency conversion across platforms — existing

### Active

*(All v1.0 requirements validated — see Validated section)*

### Validated (Phase 4 complete — 2026-03-25)

- ✓ BrainSuite API integration — POST asset + metadata, receive score + dimensions, store results (Phase 3)
- ✓ Creative scoring visible in dashboard — score badge, CE dimension tab, sort/filter by score range (Phase 3–4)
- ✓ Production security hardening — httpOnly cookie auth, encrypted tokens, path traversal fix (Phase 2)
- ✓ Platform data reliability — health badges, reconnect prompts, token_expiry exposed, SCHEDULER_ENABLED guard (Phase 3–4)
- ✓ Dashboard UX polish — thumbnail fallback, score range slider, nullslast sort, total_score alias (Phase 4)

### Out of Scope

- Real-time notifications — not requested, defer to v2
- Mobile app — web-first
- Audience/targeting asset import — user specified images and video only
- Ad copy / text creative scoring — not in scope for v1

## Context

The codebase is a brownfield Angular 17 + FastAPI application with significant functionality already built. All 4 platform OAuth flows and background sync services exist. The frontend dashboard is mostly working. The primary missing piece is the BrainSuite integration — sending creative assets + metadata to the BrainSuite API and displaying the returned score + dimension breakdown in the UI.

Key technical notes:
- Backend: FastAPI + SQLAlchemy async + PostgreSQL; deployed on Replit Autoscale
- Frontend: Angular 17 standalone components + NgRx + ECharts
- Storage: Google Cloud Storage for creative assets
- In-memory OAuth session store (`_oauth_sessions`) must be replaced before production
- JWT tokens currently stored in localStorage — security risk for production
- 69 instances of `any` type in frontend — lower priority but worth tracking
- APScheduler handles background sync; Redis is configured but unused

## Constraints

- **Deployment**: Docker Compose on any host — Phase 01 complete, fully portable (Redis, MinIO, Postgres, backend, frontend)
- **Auth**: BrainSuite API accepts asset URL + metadata (exact schema TBD from BrainSuite docs)
- **Storage**: Assets already in Google Cloud Storage — BrainSuite integration should reference stored URLs, not re-upload
- **Audience**: Internal-first, then client-facing — production hardening must happen before external users onboard

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Angular 17 + FastAPI stack | Already built — brownfield project | — Existing |
| Google Cloud Storage for assets | Replit integration built-in | — Existing |
| Score + dimensions (not just score) | User confirmed this is what BrainSuite returns | — Pending |
| Image + video only (not copy/audiences) | User scoped to creative assets only | — Pending |
| Production-ready as v1 goal | Real users onboarding — no shortcuts on security | — Pending |

---
*Last updated: 2026-03-20 after Phase 01 (infrastructure-portability) complete*
