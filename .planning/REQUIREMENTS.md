# Requirements: BrainSuite Platform Connector

**Defined:** 2026-03-20
**Core Value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## v1 Requirements

### Infrastructure & Portability

- [x] **INFRA-01**: Application runs locally via Docker Compose with no Replit dependencies
- [x] **INFRA-02**: Application deploys on any cloud provider via standard container stack
- [x] **INFRA-03**: All Replit-specific build scripts (build.sh, replit_start.sh) replaced with portable equivalents
- [x] **INFRA-04**: Replit object storage sidecar removed; replaced with S3-compatible storage (local filesystem for dev, MinIO/S3 for production)
- [x] **INFRA-05**: Replit credential exchange sidecar (http://127.0.0.1:1106) removed; replaced with standard service account / env var auth
- [x] **INFRA-06**: Redis runs as a standard Docker Compose service (no Replit sidecar dependency)
- [x] **INFRA-07**: All environment variables documented in a portable .env.example; no Replit-specific env vars required
- [x] **INFRA-08**: Interactive setup script (or guided documentation) that prompts for all required secrets (DB credentials, JWT secret, Fernet key, OAuth app credentials, BrainSuite API key, storage config) and generates a valid .env file

### Security & Code Quality

- [ ] **SEC-01**: OAuth session state stored in Redis with TTL (replace in-memory `_oauth_sessions` dict)
- [x] **SEC-02**: JWT access token stored in Angular service memory only; refresh token in httpOnly + Secure + SameSite=Lax cookie (remove all localStorage JWT storage)
- [ ] **SEC-03**: Fernet key validated at startup — app fails fast if TOKEN_ENCRYPTION_KEY is missing or invalid format
- [ ] **SEC-04**: Asset endpoint path traversal vulnerability fixed (pathlib validation on object_path in main.py)
- [ ] **SEC-05**: OAuth redirect URI hardened — not constructable from untrusted request headers (x-forwarded-host validation)
- [ ] **SEC-06**: CORS origins locked to explicit allowlist (no wildcard in production)
- [ ] **QUAL-01**: All broad `except Exception` blocks replaced with specific exception types and structured logging
- [ ] **QUAL-02**: Frontend `any` types eliminated — typed interfaces defined for all API response DTOs
- [ ] **QUAL-03**: Backend error responses follow a consistent structure across all endpoints
- [ ] **QUAL-04**: All identified bugs from codebase audit fixed (Fernet silent fallback, OAuth session cleanup, token refresh failure handling)

### BrainSuite Scoring

- [ ] **SCORE-01**: `creative_score_results` table with scoring state machine (UNSCORED → PENDING → PROCESSING → COMPLETE | FAILED)
- [ ] **SCORE-02**: `BrainSuiteScoreService` — async httpx client with tenacity retry (429 = long backoff, 5xx = short backoff, 4xx = no retry)
- [ ] **SCORE-03**: Fresh GCS/S3 signed URLs generated per scoring request (not stored URLs)
- [ ] **SCORE-04**: APScheduler scoring job runs every 15 minutes, batches up to 20 UNSCORED assets, respects rate limits
- [ ] **SCORE-05**: New assets automatically queued as UNSCORED after platform sync completes
- [ ] **SCORE-06**: Manual re-score trigger available per creative via UI and API endpoint
- [ ] **SCORE-07**: Score dimensions stored and retrievable per creative (exact schema confirmed via API discovery spike at phase start)
- [ ] **SCORE-08**: Scoring status endpoint (`/scoring/status`) for frontend polling

### Dashboard

- [ ] **DASH-01**: Creative thumbnail (image or video frame) visible per creative in list/table view
- [ ] **DASH-02**: BrainSuite score badge visible per creative in list/table view
- [ ] **DASH-03**: Score dimension breakdown panel accessible per creative (expandable or side panel)
- [ ] **DASH-04**: Creatives sortable by score, ROAS, CTR, spend
- [ ] **DASH-05**: Creatives filterable by platform, date range, and score range

### Reliability

- [ ] **REL-01**: Last sync time and connection health displayed per platform
- [ ] **REL-02**: Failed syncs and expired platform tokens surfaced to user with reconnect prompt
- [ ] **REL-03**: APScheduler runs on exactly one worker (SCHEDULER_ENABLED env var guard for multi-worker Autoscale / cloud deployments)

## v2 Requirements

### Dashboard Enhancements

- **DASH-v2-01**: Score-to-ROAS correlation view (scatter or table linking BrainSuite score to actual ROAS)
- **DASH-v2-02**: Top/bottom performer highlighting in creative grid
- **DASH-v2-03**: Score trend over time per creative

### Notifications

- **NOTF-v2-01**: User notified (in-app or email) when scoring completes for a batch
- **NOTF-v2-02**: User notified when platform sync fails

### Backfill

- **SCORE-v2-01**: Backfill scoring job for historical assets synced before BrainSuite integration existed

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time notifications (Slack/email) | Deferred to v2 |
| White-label reports | Not requested, high complexity |
| Ad copy / text creative scoring | User explicitly out of scope |
| Audience / targeting asset import | User explicitly out of scope |
| Mobile app | Web-first |
| Creative identity across platforms (same creative on Meta + TikTok) | Deferred to v2 |
| Replit deployment | Replaced by portable Docker Compose + cloud container approach |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| INFRA-07 | Phase 1 | Complete |
| INFRA-08 | Phase 1 | Complete |
| SEC-01 | Phase 2 | Pending |
| SEC-02 | Phase 2 | Complete |
| SEC-03 | Phase 2 | Pending |
| SEC-04 | Phase 2 | Pending |
| SEC-05 | Phase 2 | Pending |
| SEC-06 | Phase 2 | Pending |
| QUAL-01 | Phase 2 | Pending |
| QUAL-02 | Phase 2 | Pending |
| QUAL-03 | Phase 2 | Pending |
| QUAL-04 | Phase 2 | Pending |
| SCORE-01 | Phase 3 | Pending |
| SCORE-02 | Phase 3 | Pending |
| SCORE-03 | Phase 3 | Pending |
| SCORE-04 | Phase 3 | Pending |
| SCORE-05 | Phase 3 | Pending |
| SCORE-06 | Phase 3 | Pending |
| SCORE-07 | Phase 3 | Pending |
| SCORE-08 | Phase 3 | Pending |
| DASH-01 | Phase 4 | Pending |
| DASH-02 | Phase 4 | Pending |
| DASH-03 | Phase 4 | Pending |
| DASH-04 | Phase 4 | Pending |
| DASH-05 | Phase 4 | Pending |
| REL-01 | Phase 4 | Pending |
| REL-02 | Phase 4 | Pending |
| REL-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34/34 ✓
- Unmapped: 0

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after roadmap creation — coverage count corrected to 34*
