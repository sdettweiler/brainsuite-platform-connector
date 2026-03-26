# Production Checklist

This checklist must be completed before deploying to production or enabling live scoring
for external users.

---

## PROD-01: BrainSuite Credentials

- [ ] `BRAINSUITE_CLIENT_ID` and `BRAINSUITE_CLIENT_SECRET` set in production environment
- [ ] Credentials authenticate against Video endpoint (`ACE_VIDEO_SMV_API`) — confirmed in Phase 3
- [ ] Credentials authenticate against Static endpoint (`ACE_STATIC_SOCIAL_STATIC_API`) — confirm via discovery spike
- [ ] Run `BRAINSUITE_CLIENT_ID=<id> BRAINSUITE_CLIENT_SECRET=<secret> python scripts/spike_static_api.py`
- [ ] Spike exits 0 and prints "PROD-01: BrainSuite credentials authenticate against Static endpoint — CONFIRMED"
- [ ] `docs/spike_static_response.json` created with full response from a successful Static API job
- [ ] Confirmed via discovery spike on: [DATE — fill in after running spike]

**Note:** Both Video and Static endpoints use the same credentials (D-15). No new env vars needed.

---

## PROD-02: Google Ads OAuth Consent Screen

- [ ] Navigate to Google Cloud Console > APIs & Services > OAuth consent screen
- [ ] Verify Publishing status is "Published" (not "Testing")
- [ ] If "Testing": click "Publish App" and complete verification process
- [ ] Document the verified status and date below

**Status:** [PENDING VERIFICATION — requires manual check in Google Cloud Console]

**Verification steps:**
1. Go to https://console.cloud.google.com/
2. Select the project used for this application
3. Navigate to APIs & Services > OAuth consent screen
4. Check the "Publishing status" field
5. If "Testing": external users cannot complete OAuth — must publish before go-live
6. If "Published": confirm user type is "External" and no verification errors shown

**Verified by:** [Name]
**Date:** [Date]
**Result:** [Published / Testing — action taken]

---

## PROD-03: Environment Configuration

- [ ] `TOKEN_ENCRYPTION_KEY` set (32-byte url-safe base64 Fernet key)
- [ ] `SECRET_KEY` set (random, at least 32 characters)
- [ ] `DATABASE_URL` and `SYNC_DATABASE_URL` point to production PostgreSQL
- [ ] `REDIS_URL` points to production Redis instance
- [ ] `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` set for production storage
- [ ] `BASE_URL` set to production domain (used for OAuth callbacks — must be exact)
- [ ] `FRONTEND_URL` set to production domain
- [ ] `SCHEDULER_ENABLED=true` on exactly one worker (not all workers in multi-worker deployments)
- [ ] `CURRENT_ENV=production` (ensures dev credential fallback is disabled)

---

## PROD-04: Alembic Migrations

- [ ] All Alembic migrations applied: `alembic upgrade head`
- [ ] Verify `endpoint_type` column exists on `creative_score_results` (Phase 5 migration)
- [ ] Existing rows backfilled: `SELECT COUNT(*) FROM creative_score_results WHERE endpoint_type IS NULL` returns 0

---

## PROD-05: Platform OAuth Apps

- [ ] Meta: App ID + Secret configured, redirect URI registered in Meta App Dashboard
- [ ] TikTok: App ID + Secret configured, redirect URI registered
- [ ] Google Ads: Client ID + Secret + Developer Token configured, redirect URI in Google Cloud Console
- [ ] DV360: Client ID + Secret configured (shared with Google Ads or separate)
