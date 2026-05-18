# Roadmap: BrainSuite Platform Connector

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-25) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Insights + Intelligence** — Phases 5–10 (shipped 2026-04-15) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 BrainSuite Configuration** — Phases 11–14 (shipped 2026-04-28) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 SuperAdmin Monitoring & TikTok Downloads** — Phases 15–19.3 (shipped 2026-05-13) — [archive](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 YouTube Downloads & Dashboard Filters** — Phases 20–23 (shipped 2026-05-18) — [archive](milestones/v1.4-ROADMAP.md)
- 🚧 **v1.5 Download Performance & Tech Debt** — Phases 24–26 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-25</summary>

- [x] **Phase 1: Infrastructure Portability** (3/3 plans) — completed 2026-03-20
- [x] **Phase 2: Security Hardening** (6/6 plans) — completed 2026-03-23
- [x] **Phase 3: BrainSuite Scoring Pipeline** (6/6 plans) — completed 2026-03-24
- [x] **Phase 4: Dashboard Polish + Reliability** (4/4 plans) — completed 2026-03-25

</details>

<details>
<summary>✅ v1.1 Insights + Intelligence (Phases 5–10) — SHIPPED 2026-04-15</summary>

- [x] **Phase 5: BrainSuite Image Scoring** (4/4 plans) — completed 2026-03-27
- [x] **Phase 6: Historical Backfill + Score History Schema** (1/1 plans) — completed 2026-03-30
- [x] **Phase 7: Score Trend, Performer Highlights + Performance Tab** (3/3 plans) — completed 2026-03-30
- [x] **Phase 8: Score-to-ROAS Correlation** (2/2 plans) — completed 2026-03-31
- [x] **Phase 9: AI Metadata Auto-Fill** (3/3 plans) — completed 2026-04-15
- [x] **Phase 10: In-App Notifications** (2/2 plans) — completed 2026-04-15

</details>

<details>
<summary>✅ v1.2 BrainSuite Configuration (Phases 11–14) — SHIPPED 2026-04-28</summary>

- [x] **Phase 11: Per-Org Config Schema + Pipeline Wiring** (3/3 plans) — completed 2026-04-16
- [x] **Phase 12: Credentials + App Name Settings UI** (3/3 plans) — completed 2026-04-17
- [x] **Phase 13: Field Mapping Editor + Mandatory Field Enforcement** (4/4 plans) — completed 2026-04-21
- [x] **Phase 14: YouTube Cookies Admin UI** (3/3 plans) — completed 2026-04-27

</details>

<details>
<summary>✅ v1.3 SuperAdmin Monitoring & TikTok Downloads (Phases 15–19.3) — SHIPPED 2026-05-13</summary>

- [x] **Phase 15: TikTok Asset Download** (2/2 plans) — completed 2026-05-08
- [x] **Phase 16: Job Persistence Schema** (3/3 plans) — completed 2026-05-08
- [x] **Phase 17: Service Instrumentation** (6/6 plans) — completed 2026-05-11
- [x] **Phase 18: SSE Transport** (2/2 plans) — completed 2026-05-11
- [x] **Phase 19: SuperAdmin Monitoring UI** (6/6 plans) — completed 2026-05-11
- [x] **Phase 19.1: Close gap: BLOCKER-02+03** (1/1 plans) — completed 2026-05-13
- [x] **Phase 19.2: Close gap: INSTR-05/MON-07** (1/1 plans) — completed 2026-05-13
- [x] **Phase 19.3: Close gap: Phase 15** (2/2 plans) — completed 2026-05-13

</details>

<details>
<summary>✅ v1.4 YouTube Downloads & Dashboard Filters (Phases 20–23) — SHIPPED 2026-05-18</summary>

- [x] **Phase 20: Proxy Download Infrastructure** (2/2 plans) — completed 2026-05-15
- [x] **Phase 21: Proxy Admin UI** (3/3 plans) — completed 2026-05-15
- [x] **Phase 22: Dashboard Metadata + Account Filters** (2/2 plans) — completed 2026-05-15
- [x] **Phase 23: Dashboard Duration Filter + Backfill** (2/2 plans) — completed 2026-05-18

</details>

### v1.5 Download Performance & Tech Debt (Phases 24–26)

- [x] **Phase 24: Download Performance Backend** (3 plans) - Backend-only optimizations: extraction/download split, PO-first retry, proxy config cache, DV360 sleep reduction, socket timeout tuning (completed 2026-05-18)
- [ ] **Phase 25: Configurable Concurrency** - SuperAdmin UI + backend semaphore for max_concurrent_downloads
- [ ] **Phase 26: Tech Debt Closure** - Alembic 4-head merge + Google Ads live download validation

## Phase Details

### Phase 24: Download Performance Backend
**Goal**: DV360 and Google Ads video downloads complete 3–5x faster by routing only stream bytes through the proxy, executing proxy calls in an optimized retry order, and eliminating connection and sleep bottlenecks
**Depends on**: Phase 23 (proxy download infrastructure established)
**Requirements**: PERF-01, PERF-03, PERF-04, PERF-05, PERF-06
**Success Criteria** (what must be TRUE):
  1. A DV360 download job completes in measurably less wall-clock time — proxy overhead of 7–15s per video is gone because yt-dlp info extraction runs direct and only stream bytes touch the proxy
  2. A download attempt with a PO token succeeds without ever routing through the residential proxy when the video is publicly accessible — proxy is reserved for the fallback path
  3. A stuck proxy connection fails within 10 seconds and the job continues to the next asset rather than blocking the download queue for up to 30 seconds
  4. DV360 downloads do not pause between assets when proxy sticky-session pinning is active — no artificial inter-download sleep visible in job logs
  5. The proxy config (URL + enabled flag) is read from DB and decrypted at most once per 60-second window regardless of how many concurrent download calls are in flight
**Plans**: 3 plans
- [x] 24-01-PLAN.md — proxy_cache.py module with 60s TTL get_proxy_config() + unit tests (foundational, Wave 1)
- [x] 24-02-PLAN.md — dv360_sync.py refactor: extraction/download split, PO-first retry, conditional batch sleep, socket_timeout=10 (Wave 2)
- [x] 24-03-PLAN.md — google_ads_sync.py parity refactor: split, PO-first, remote_components fix (D-05), socket_timeout=10 (Wave 2)

### Phase 25: Configurable Concurrency
**Goal**: SuperAdmin can tune maximum parallel downloads via the admin UI, and all platforms (DV360 and Google Ads) respect the limit via a shared asyncio semaphore
**Depends on**: Phase 24 (download call chain established before semaphore wraps it)
**Requirements**: PERF-02
**Success Criteria** (what must be TRUE):
  1. A SuperAdmin can open /configuration/admin and set max concurrent downloads to any integer between 1 and 10; the setting persists across server restarts
  2. When max_concurrent_downloads is set to 1 and two download jobs run simultaneously, the second job's downloads visibly queue behind the first in the monitoring UI rather than both executing in parallel
  3. A fresh install with no explicit configuration defaults to 3 concurrent downloads without requiring any manual admin action
  4. Changing the concurrency setting in the UI takes effect for the next download job without a server restart
**Plans**: 3 plans
- [ ] 25-01-PLAN.md — SystemConfig.max_concurrent_downloads column + Alembic migration + proxy_cache.get_concurrency_semaphore() with 60s TTL + unit tests (Wave 1)
- [ ] 25-02-PLAN.md — Wrap DV360 + Google Ads _do_download with semaphore + GET/PUT /super-admin/download-concurrency endpoints + endpoint tests (Wave 2)
- [ ] 25-03-PLAN.md — Admin UI restructure: merge Residential Proxy + YouTube Cookies into 'Download Settings' section + new Parallel Downloads mat-slider + human-verify checkpoint (Wave 3)
**UI hint**: yes

### Phase 26: Tech Debt Closure
**Goal**: A developer can run `alembic upgrade head` on a fresh install without errors, and the Google Ads download pipeline is confirmed working end-to-end against a real YouTube video
**Depends on**: Phase 24, Phase 25 (all migrations for v1.5 must exist before merge)
**Requirements**: DEBT-01, PROXY-02
**Success Criteria** (what must be TRUE):
  1. Running `alembic upgrade head` on a clean database with no prior migrations completes without a "multiple heads" ambiguity error
  2. Running `alembic history` shows a single linear chain with no branch points
  3. A Google Ads sync job downloads at least one real YouTube video asset end-to-end in the production-like environment, with the asset appearing in MinIO/S3 storage
  4. The Google Ads download job log shows the same proxy/PO-token retry sequence that DV360 uses — confirming code path parity
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Portability | v1.0 | 3/3 | Complete | 2026-03-20 |
| 2. Security Hardening | v1.0 | 6/6 | Complete | 2026-03-23 |
| 3. BrainSuite Scoring Pipeline | v1.0 | 6/6 | Complete | 2026-03-24 |
| 4. Dashboard Polish + Reliability | v1.0 | 4/4 | Complete | 2026-03-25 |
| 5. BrainSuite Image Scoring | v1.1 | 4/4 | Complete | 2026-03-27 |
| 6. Historical Backfill + Score History Schema | v1.1 | 1/1 | Complete | 2026-03-30 |
| 7. Score Trend, Performer Highlights + Performance Tab | v1.1 | 3/3 | Complete | 2026-03-30 |
| 8. Score-to-ROAS Correlation | v1.1 | 2/2 | Complete | 2026-03-31 |
| 9. AI Metadata Auto-Fill | v1.1 | 3/3 | Complete | 2026-04-15 |
| 10. In-App Notifications | v1.1 | 2/2 | Complete | 2026-04-15 |
| 11. Per-Org Config Schema + Pipeline Wiring | v1.2 | 3/3 | Complete | 2026-04-16 |
| 12. Credentials + App Name Settings UI | v1.2 | 3/3 | Complete | 2026-04-17 |
| 13. Field Mapping Editor + Mandatory Field Enforcement | v1.2 | 4/4 | Complete | 2026-04-21 |
| 14. YouTube Cookies Admin UI | v1.2 | 3/3 | Complete | 2026-04-27 |
| 15. TikTok Asset Download | v1.3 | 2/2 | Complete | 2026-05-08 |
| 16. Job Persistence Schema | v1.3 | 3/3 | Complete | 2026-05-08 |
| 17. Service Instrumentation | v1.3 | 6/6 | Complete | 2026-05-11 |
| 18. SSE Transport | v1.3 | 2/2 | Complete | 2026-05-11 |
| 19. SuperAdmin Monitoring UI | v1.3 | 6/6 | Complete | 2026-05-11 |
| 19.1. Close gap: BLOCKER-02+03 | v1.3 | 1/1 | Complete | 2026-05-13 |
| 19.2. Close gap: INSTR-05/MON-07 | v1.3 | 1/1 | Complete | 2026-05-13 |
| 19.3. Close gap: Phase 15 | v1.3 | 2/2 | Complete | 2026-05-13 |
| 20. Proxy Download Infrastructure | v1.4 | 2/2 | Complete | 2026-05-15 |
| 21. Proxy Admin UI | v1.4 | 3/3 | Complete | 2026-05-15 |
| 22. Dashboard Metadata + Account Filters | v1.4 | 2/2 | Complete | 2026-05-15 |
| 23. Dashboard Duration Filter + Backfill | v1.4 | 2/2 | Complete | 2026-05-18 |
| 24. Download Performance Backend | v1.5 | 3/3 | Complete   | 2026-05-18 |
| 25. Configurable Concurrency | v1.5 | 0/3 | Planning | - |
| 26. Tech Debt Closure | v1.5 | 0/? | Not started | - |

## Backlog

- **999.1** Dashboard metadata filter with autocomplete — built in Apr 2026 (commits 1d8edb6, aa9273f), lost in later session; recover from git history — **addressed in Phase 22**
- **999.2** Dashboard ad account multi-select filter — verify still present (last seen in commits e403eaf-d05999e); if lost, recover from git history — **addressed in Phase 22**
