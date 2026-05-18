# Requirements — v1.5 Download Performance & Tech Debt

*Generated: 2026-05-18*

## This Milestone

### Download Performance

- [x] **PERF-01**: User's YouTube video downloads complete faster because yt-dlp info extraction runs direct (no proxy) while only the actual video stream bytes route through the residential proxy — eliminates 7–15s of proxy overhead per video
- [ ] **PERF-02**: SuperAdmin can configure max concurrent downloads per sync batch (default 3, range 1–10) via a setting in the SuperAdmin UI; all platforms (DV360 + Google Ads) respect the limit via a shared asyncio semaphore
- [x] **PERF-03**: System attempts PO-token cookieless download first (no proxy), then PO+proxy, then cookies+proxy — reduces proxy calls for public ad creatives that don't require authentication
- [x] **PERF-04**: Decrypted proxy config (URL + enabled flag) is cached in application memory with a 60-second TTL so the database and Fernet decryption are not invoked on every individual download call
- [x] **PERF-05**: DV360 inter-download sleep is dropped (or reduced to ≤1s) when residential proxy with sticky-session pinning is active — session pinning replaces the need for the artificial delay
- [x] **PERF-06**: socket_timeout for all proxy-routed yt-dlp calls is set to 10 seconds (reduced from 30s) so stuck proxy connections fail fast rather than blocking the download queue

### Tech Debt

- [ ] **DEBT-01**: Developer can run `alembic upgrade head` on a fresh install without encountering a multiple-heads ambiguity error — all 4 migration head branches are merged into a single linear history
- [ ] **PROXY-02**: Google Ads live download pipeline completes a real YouTube video download end-to-end in a production-like environment (validates the code path, which is identical to DV360's path that passed v1.4 UAT; requires unblocking MCC/cookie environment issues)

## Future Requirements

- 720p format quality cap (user declined for v1.5 — revisit if bandwidth costs become a concern)
- Account-level metadata defaults: connection_metadata_defaults table + account config UI + lookup fallback (META-01, META-02)
- SSE Redis pub/sub upgrade at 50+ concurrent SuperAdmins (SSE-03)
- TikTok live-run UAT confirmation (TKTOK-01/02 — live sync environment required)
- Dashboard filter state URL persistence

## Out of Scope

- 720p quality cap — full quality maintained for all downloads; no lossy format selection
- Mobile app
- Real-time notifications (Slack/email)
- Creative identity across platforms (v2)

## Traceability

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| PERF-01 | Phase 24 | Download Performance Backend |
| PERF-02 | Phase 25 | Configurable Concurrency |
| PERF-03 | Phase 24 | Download Performance Backend |
| PERF-04 | Phase 24 | Download Performance Backend |
| PERF-05 | Phase 24 | Download Performance Backend |
| PERF-06 | Phase 24 | Download Performance Backend |
| DEBT-01 | Phase 26 | Tech Debt Closure |
| PROXY-02 | Phase 26 | Tech Debt Closure |
