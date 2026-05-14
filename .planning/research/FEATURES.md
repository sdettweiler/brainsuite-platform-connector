# Feature Landscape

**Domain:** Creative analytics dashboard for ad agencies (performance marketing)  
**Researched:** 2026-05-14 (v1.4 YouTube/DV360 proxy + dashboard filters added)  
**Confidence:** HIGH (v1.3 monitoring patterns) + MEDIUM–HIGH (v1.4 proxy workflow + filter UX patterns)

---

## v1.4 Feature Research — YouTube/DV360 Residential Proxy + Dashboard Filters

This section covers two feature tracks: (1) residential proxy integration for YouTube/Google Ads/DV360 video downloads on cloud infrastructure, and (2) three dashboard filters (metadata autocomplete, ad account multi-select, video duration range).

---

### Proxy Download Track: Table Stakes

Features users expect for video creative downloads to work reliably in production cloud environments (GCP, AWS, etc.).

| Feature | Why Expected | Complexity | Implementation Notes |
|---------|--------------|------------|----------------------|
| **Residential proxy URL injection into yt-dlp options** | YouTube blocks datacenter IPs (GCP Cloud Run, etc.) — residential proxies are the only solution that works at scale. Without this, all video downloads fail on production hosts. | Med | Proxy URL passed to yt-dlp as `--proxy "http://user:password@host:port"`. Existing cookie auth layer remains; proxy is an additional layer. Provider: Webshare (validation), IPRoyal (production). |
| **Sticky session per download job** | Multiple concurrent downloads need isolation — each job gets a unique session ID embedded in proxy username (e.g., `user-job123456@host:port`) so exit IP stays consistent for that download across all internal requests (metadata fetch, format parsing, chunks). | Med | Session ID generated per BackgroundJob, not per HTTP request. Proxy provider uses session ID to assign + stick exit IP for job duration. Prevents mid-download IP rotation that breaks YouTube's internal consistency checks. |
| **PO token generation via bgutil plugin** | YouTube's BotGuard attestation layer now requires PO tokens for video metadata and segment requests on most clients. Without PO token integration, yt-dlp fails with 403 on format list or streaming. | High | bgutil HTTP server (port 4416, always-running) or script mode (slower, not recommended). Token is video-ID-bound (new token per video). Token lifetime ~12 hours to several months (varies by YouTube). PO token injected into yt-dlp options. |
| **Three-layer stack working end-to-end** | Proxy layer (IP unblocking) → Cookie layer (auth state) → PO token layer (bot attestation). All three are necessary; each failure mode is a different root cause. | High | Stacked architecture: (1) yt-dlp connects via residential proxy IP, (2) uses stored YouTube cookie if available, (3) requests PO token from bgutil, (4) executes download. Each layer independently testable but all three required for production reliability. |
| **Admin toggle to enable/disable proxy + token generation** | SuperAdmins must control when residential proxy costs accrue (per-download billing). Fallback: download without proxy (fails on GCP, succeeds on residential networks). Admin UI provides binary on/off. | Low | SystemConfig singleton row: `residential_proxy_enabled` (boolean). When false, skip proxy URL injection and token generation. Cookie layer always available as fallback. |
| **Encrypted proxy URL storage in SuperAdmin panel** | URL contains auth credentials (username:password). Cannot be logged, exposed in error messages, or stored in plaintext. Same Fernet encryption used for YouTube cookies. | Low | SystemConfig.residential_proxy_url (String(1000), Fernet-encrypted). Backend decrypts at download time, passes to yt-dlp. Frontend UI masks input (password type). |

### Proxy Download Track: Differentiators (Nice to Have)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-provider cost tracking dashboard** | Display cumulative residential proxy bytes/sessions consumed (for budget planning). Different providers have different pricing models. | High | Requires provider API integration for usage stats. Deferred to v1.5 if needed for cost forecasting. |
| **Automatic provider failover** | If primary provider (IPRoyal) is unreachable, fallback to secondary (Webshare). Graceful degradation under provider outage. | High | Requires health checks + failover logic. Complex state machine. Deferred to v1.5. |
| **Per-platform proxy configuration** | Different proxy providers for DV360 vs Google Ads vs YouTube native. Provider A works better for certain geo-restrictions. | Med | Requires separate URL fields per platform. Nice-to-have for global agencies, but v1.4 uses single unified proxy. |
| **Download retry with exponential backoff + circuit breaker** | Transient failures (timeout, IP block) trigger automatic retry. After N failures, circuit breaker opens to prevent resource exhaustion. | Med | Retry loop with jitter; circuit breaker state persisted to DB. Standard reliability pattern. Consider if backlog of stuck jobs accumulates. |
| **Proxy request logging (non-credential)** | Log session ID, provider, exit IP (if available via API), timestamp for debugging. Helps correlate failures to specific proxy behavior. | Low | Structured logging to stderr/JSON. Session ID is the primary debug key. Non-sensitive and valuable for support. |

### Proxy Download Track: Anti-Features (Don't Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Per-request session rotation** | Tempting to rotate exit IP on every HTTP request within a single download (metadata, chunks, etc.). This breaks YouTube's internal consistency checks—segments must come from same IP. | Stick session ID to entire download job. Single exit IP per job. YouTube's architecture assumes continuity. |
| **Unencrypted proxy URL in .env** | Environment variables are version-controlled, visible in logs, shared across environments. Credentials should never be in code. | Always use SystemConfig singleton with Fernet encryption (existing pattern). Backend reads at runtime. |
| **Manual token extraction + caching** | PO tokens are video-ID-bound and short-lived. Manual extraction of a token and reusing across videos fails. Tempting to reduce API calls but impossible at scale. | Use bgutil HTTP server — it handles generation + caching per-video. Let it manage token lifecycle. |
| **Proxy + Cookie fallback chain** | "Try proxy+cookie first, then proxy-only, then cookie-only, then no auth." Each attempt is a time cost. Too many fallback layers introduce latency and confusion. | Three-layer stack is final: proxy (always) → cookie (if available) → token (if available). Fail fast if any layer has config issues. |
| **Rotating proxy per metadata request** | Similar to per-request rotation within a single download. Different metadata endpoints need same IP context. | Sticky session for entire job including metadata fetch phase. |
| **Proxy URL in response bodies or error messages** | Security smell. Even partial URLs (masked username) can leak provider infrastructure. | Sanitize all error messages. Never return proxy config to frontend. Log session ID only, not credentials. |

---

### Dashboard Filters Track: Table Stakes

Features users expect to narrow the creative grid effectively. Missing any of these = dashboard feels incomplete without filtering capability.

| Feature | Why Expected | Complexity | Implementation Notes |
|---------|--------------|------------|----------------------|
| **Metadata autocomplete filter** | User types partial text (e.g., "en_" in language field) and sees matching metadata values (en_US, en_GB, etc.). Essential for dashboards with 100+ unique metadata values per field — scrolling a 100-item dropdown is unusable. Debounce prevents API hammering. | Med | Input with `(input)` event → debounce(300ms) → query backend for matches → show dropdown. Min 2 characters typed before search fires. Loading spinner during fetch. Works on brand, language, creator, category, etc. Powered by existing harmonized metadata columns. |
| **Ad account multi-select filter** | User selects 1+ ad accounts (Meta, TikTok, DV360, Google Ads) to narrow creative grid. Expected because users have 5–20 connected accounts and want to filter to single account or subset. | Low–Med | Dropdown with checkboxes OR Material chips (after selection). Existing `account_id` column indexed. Query applies `WHERE account_id IN (...)`. Visual indicator (badge) shows number of selected accounts. Checkboxes faster (6s vs 9s for chips), so checkboxes if >5 accounts; chips if <5 (visual polish). |
| **Video duration range slider** | User sets min/max duration in seconds (e.g., "15–60s") to filter creatives. Essential because video length is a core creative attribute affecting performance, CTR, completion rate. | Med | Dual-handle range slider (ngx-slider 17.0.2 already installed). Floor = 0s, ceiling = 3600s (1 hour). Step = 5 or 15 seconds. Display selected range in text below slider (e.g., "15–60 seconds"). Reset button clears filter. Applies `WHERE duration_seconds >= min AND duration_seconds <= max`. |
| **Filter persistence across pagination/sorting** | User applies filters, sorts by score, paginates; filters stay active. | Low | Store filter state in component TS (not URL params initially — can add URL params in v1.5 for bookmarkability). Reapply filters to every query. |
| **Clear filters button** | Reset all active filters to default state (show all creatives). | Low | Single button or "Clear all" link. Sets component filter arrays to empty, re-queries dashboard grid. |

### Dashboard Filters Track: Differentiators (Nice to Have)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Autocomplete filter with "all values" preset** | Show `(All)` option at top of dropdown so user can quickly select all + deselect as needed. Useful for "I want everything except brand X" scenarios. | Low | Add `{label: '(All)', value: null}` to dropdown options. Selecting it clears the filter. |
| **Saved filter presets** | User saves "Video only, Meta accounts, 15–60s duration" as a preset and re-applies it with one click. | High | Requires new table: `dashboard_filter_presets` with org_id, name, filter_json, created_at. Complex state management. Deferred to v1.5. |
| **Metadata filter "other" grouping** | Collapse rare values (e.g., languages with <5 creatives) under "Other" to shorten dropdown. | Med | Calculate cardinality; threshold to "Other" group. Nice for very large metadata domains. |
| **Duration range presets** | Quick buttons: "0–15s", "15–30s", "30–60s", "60s+" instead of manual slider drag. | Low | Buttons above slider that set min/max to preset values. Standard UX pattern. |
| **Autocomplete filters show asset count** | In dropdown: "en_US (47 creatives)" so user knows filter impact before applying. | Low | Requires count subquery per option. Marginal UX gain; deferred if performance is a concern. |
| **Filter tag chips with remove buttons** | After filtering, show "Meta [x]", "en_US [x]", "15–60s [x]" chips at top of grid. User can remove individual filter by clicking X. | Low | Show active filters as Material chips with matChipRemove directive. Visually clear what's applied. Standard pattern. |

### Dashboard Filters Track: Anti-Features (Don't Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Autocomplete with <2 character minimum** | Every keystroke triggers query. At 1 character, metadata dropdowns return 50–100 values (e.g., all metadata starting with "a"). API load spikes unnecessarily. | Enforce min 2 characters before firing search. User types a phrase to narrow down. |
| **Slider with step < 5 seconds** | Users cannot meaningfully adjust duration in 1-second increments for creative filtering. Too granular. Causes slider handle to be janky. | Use step = 5 or 15 seconds. User-friendly ranges. |
| **Multi-select checkboxes for 50+ options** | Dropdown becomes a 50-item scrollable list of checkboxes. Unusable. Cognitive overload. UX breaks. | Use autocomplete (filtered search) for large option sets. Checkboxes work for <10 options (single account filter, simple categories). |
| **Autocomplete that searches on every keystroke without debounce** | Network waterfall. Backend API gets hammered. Latency >500ms per keystroke = janky UX. Aggravates infrastructure costs. | Always debounce: wait 300ms after user stops typing, then fire single request. |
| **Filter state in URL query params (v1.4)** | URL-first filtering adds complexity: serialization, deserialization, browser history collisions, bookmark issues. Not worth the complexity for internal filtering at v1.4 scale. | Keep filter state in component TS for v1.4. Filters apply to current session only. Add URL params in v1.5 if bookmarkability is a user request. |
| **Numeric text input fields for duration instead of slider** | "Min seconds: [__]  Max seconds: [__]" requires typing. Slider is faster (drag to adjust) and more intuitive for ranges. | Use dual-handle range slider. Text inputs optional below slider for manual entry (accessibility), but slider is primary. |
| **Combining all three filters with AND logic only** | "Account = Meta AND Duration 15–60s AND Language = en_US" becomes restrictive. No option for OR (e.g., "Meta OR TikTok"). | v1.4 uses AND logic (simple intersection). OR logic is a v1.5 differentiator if users need "any of these accounts" scenarios. |

---

### v1.4 Feature Dependencies

```
Dashboard Metadata Autocomplete Filter
  ├── Existing: harmonized metadata columns populated at sync time
  └── Dependency: backend endpoint GET /dashboard/metadata/values?field=language&search=en (NEW)

Dashboard Ad Account Multi-Select Filter
  ├── Existing: account_id column indexed on CreativeAsset
  └── No new backend required (filter applied client-side or via existing filter endpoint)

Dashboard Video Duration Range Slider
  ├── Existing: duration_seconds column on CreativeAsset (from TikTok/YouTube metadata)
  ├── Existing: ngx-slider 17.0.2 already installed
  └── No new backend required (filter applied via existing filter endpoint)

Residential Proxy for YouTube Downloads
  ├── Existing: yt-dlp integration (TikTok downloads v1.3)
  ├── Existing: YouTube cookie auth via SystemConfig (v1.2)
  ├── Existing: background_jobs instrumentation (v1.3)
  └── Dependencies:
       ├── bgutil HTTP server running (external service, not in-repo)
       ├── NEW: SystemConfig.residential_proxy_enabled (boolean)
       ├── NEW: SystemConfig.residential_proxy_url (encrypted string)
       └── NEW: yt-dlp proxy URL injection at download time

SuperAdmin Proxy Config UI
  ├── Existing: /configuration/admin panel and SuperAdmin role
  ├── Existing: Fernet encryption for SystemConfig fields (YouTube cookies)
  └── NEW: UI controls for proxy enable/disable toggle + URL input
```

### v1.4 MVP Recommendation

**Phase Structure (Suggested Ordering):**

**Phase 1: Residential Proxy Infrastructure (Est. 1 day)**
- Add SystemConfig.residential_proxy_enabled, SystemConfig.residential_proxy_url (with Fernet encryption)
- Create Alembic migration
- SuperAdmin UI: toggle + encrypted URL input
- Rationale: Unblocks YouTube downloads; prerequisite for PO token integration

**Phase 2: bgutil PO Token Integration (Est. 4 days)**
- Deploy bgutil HTTP server (port 4416) in docker-compose.yml
- Update yt-dlp invocations in `download_youtube.py` to pass `--po-msos-token` (request from bgutil)
- Add retry logic for token generation failures
- Rationale: Completes three-layer stack; makes downloads reliable

**Phase 3: Dashboard Filters (Est. 4.5 days)**
- **Metadata Autocomplete:** backend endpoint + Angular debounced input + dropdown (2 days)
- **Ad Account Multi-Select:** checkboxes or Material chips (1 day)
- **Video Duration Range Slider:** ngx-slider with dual handles (1.5 days)
- Rationale: Restores filtering UX; unifies disparate features under single phase

**Total Estimated Effort: ~10 days**

### Defer to v1.5

- **Saved filter presets** — requires new table, complex state machine
- **Per-provider cost tracking** — requires provider API integration
- **Filter persistence in URL params** — bookmarkability feature, not MVP
- **Autocomplete count subquery** — marginal UX, potential perf cost

### Why This Order

1. **Proxy + PO token before filters:** Video downloads must work before users filter creatives
2. **SuperAdmin UI before internal complexity:** Ops team can test proxy + token without frontend filter churn
3. **All three filters in same phase:** Dashboard usability is a package deal; splitting filters across phases delays user benefit

---

## Confidence Assessment for v1.4

| Area | Confidence | Notes |
|------|------------|-------|
| Residential proxy workflow with yt-dlp | HIGH | Verified with yt-dlp documentation, multiple proxy provider guides (Webshare, IPRoyal, Oxylabs), and Medium/blog posts on production deployment |
| PO token lifecycle + bgutil integration | MEDIUM–HIGH | yt-dlp wiki and bgutil GitHub docs confirm token generation, HTTP server mode, and per-video token binding. Implementation details defer to phase-specific research. |
| Sticky session strategy (session ID in username) | HIGH | Standard practice in high-concurrency proxy rotation; confirmed in yt-dlp proxy guides and proxy provider documentation |
| Metadata autocomplete UX patterns | HIGH | Debouncing, min-character threshold, loading states confirmed via Algolia autocomplete guide, Metabase dashboard filters, SaaS filter design patterns |
| Ad account multi-select (checkboxes vs chips) | HIGH | Material Design 3 + e-commerce UX research confirm checkboxes (6s) vs chips (9s) performance and appropriate use cases; Angular Material implementation well-established |
| Video duration range slider | HIGH | ngx-slider 17.0.2 documented, Material Design range slider patterns, SaaS dashboard examples all confirm dual-handle slider as standard for range filtering |
| Three-layer proxy stack necessity | HIGH | YouTube's technical requirements (IP blocking, BotGuard, cookie auth) confirmed across multiple authoritative sources; stacking is industry-standard practice |

---

## Sources

### v1.4 Residential Proxy & yt-dlp
- [Scaling YouTube Video Scraping for AI with yt-dlp and Proxies](https://medium.com/@datajournal/how-to-use-yt-dlp-to-scrape-youtube-videos-with-proxies-38255a65c20d)
- [How to use Proxies for yt-dlp (HTTP, SOCKS5 & Tor)](https://www.huntapi.com/blog/yt-dlp-proxy-guide)
- [How to Use yt-dlp to Scrape YouTube Videos with Proxies](https://www.glorycloud.com/blog/yt-dlp-scarpe-videos-proxy/)
- [YouTube Downloader (yt_dlp) integration | Oxylabs Documentation](https://developers.oxylabs.io/video-data/high-bandwidth-proxies/youtube-downloader-yt_dlp-integration)

### v1.4 PO Token & bgutil
- [YouTube PO Token Guide - yt-dlp/yt-dlp Wiki](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [GitHub - Brainicism/bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- [bgutil-ytdlp-pot-provider · PyPI](https://pypi.org/project/bgutil-ytdlp-pot-provider/0.3.0/)

### v1.4 Dashboard Filters & UX Patterns
- [Debounce sources - Algolia](https://www.algolia.com/doc/ui-libraries/autocomplete/guides/debouncing-sources)
- [Mastering E-Commerce UX: Chips vs Checkboxes for Better Filters](https://valeria-pakhneva.medium.com/mastering-e-commerce-ux-chips-vs-checkboxes-for-better-filters-fae3e71d6cc1)
- [Chips – Material Design 3](https://m3.material.io/components/chips/guidelines)
- [Create a multi select chips component with Angular Material](https://zoaibkhan.com/blog/create-a-multi-select-chips-component-with-angular-material/)
- [Angular Material - Chips](https://material.angular.dev/components/chips)
- [Angular Range Slider Component | Syncfusion](https://www.syncfusion.com/angular-components/angular-slider)
- [19+ Filter UI Examples for SaaS: Design Patterns & Best Practices](https://www.eleken.co/blog-posts/filter-ux-and-ui-for-saas)
- [Dashboard filters | Metabase Documentation](https://www.metabase.com/docs/latest/dashboards/filters)
- [Should I use chip components instead of checkboxes?](https://cieden.com/book/atoms/checkbox/chip-components-or-checkboxes)

**v1.3 Job Monitoring & Admin Dashboards:**
- [Real-Time Dashboards — Jaspersoft](https://www.jaspersoft.com/articles/what-is-a-real-time-dashboard)
- [SaaS Dashboard Design Best Practices — UX Collective](https://uxdesign.cc/design-thoughtful-dashboards-for-b2b-saas-ff484385960d?gi=157f4f318b9f)
- [Progress Indicator UX/UI Design — Usersnap](https://usersnap.com/blog/progress-indicators/)
- [Progress Tracker Design Best Practices — UXPin](https://www.uxpin.com/studio/blog/design-progress-trackers/)
- [Server-Sent Events in Angular — Medium](https://codewithbilal.medium.com/implementing-server-sent-events-in-angular-a-complete-guide-05d35edc9935)
- [Monitoring Celery Guide — Cronitor](https://cronitor.io/guides/monitoring-celery)
- [Flower: Celery Monitoring — GitHub](https://github.com/mher/flower)
- [Taskforce.sh: BullMQ Dashboard — Taskforce](https://taskforce.sh/)
- [AWS S3 Batch Job Status Tracking — AWS Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops-job-status.html)
- [Batch Job Monitoring Best Practices — OneUptime](https://oneuptime.com/blog/post/2026-01-30-batch-processing-monitoring/view)
- [JSON Collapsible Display — Renderjson GitHub](https://github.com/caldwell/renderjson)
- [Error Tracking UI Patterns — DataDog](https://docs.datadoghq.com/error_tracking/)
- [Admin Dashboard UI Guide — ExtraHop](https://docs.extrahop.com/8.3/eh-admin-ui-guide/)

**v1.1 & v1.0 Research (Original Sources):**
- [Claude Vision — Official Anthropic Documentation](https://platform.claude.com/docs/en/build-with-claude/vision) — HIGH confidence
- [Creative Analytics: A Complete Guide for Performance Marketers — Improvado, 2026](https://improvado.io/blog/creative-analytics) — MEDIUM confidence
- [How to Analyze Ad Creative Performance Effectively — Segwise](https://segwise.ai/blog/analyzing-ad-creative-performance-effectively) — MEDIUM confidence
- [Analyze Creative Performance — Triple Whale Help Center](https://kb.triplewhale.com/en/articles/6362638-analyze-creative-performance-with-the-creative-analysis-dashboard) — MEDIUM confidence (official docs)
- [Master data-driven ad creative testing — Supermetrics](https://supermetrics.com/blog/ad-creative-testing-optimization) — MEDIUM confidence
- [How to Build a Global Notification Service in Angular — Medium, 2025](https://medium.com/@sehban.alam/how-to-build-a-global-notification-service-in-angular-2025-edition-b45fd487a293) — MEDIUM confidence
- [Server-sent events vs. WebSockets — LogRocket](https://blog.logrocket.com/server-sent-events-vs-websockets/) — HIGH confidence (established reference)
- [How to Predict Ad Performance Before You Spend — Madgicx](https://madgicx.com/blog/predict-ad-performance) — MEDIUM confidence
- [Data Visualization Techniques — Improvado](https://improvado.io/blog/how-to-use-data-visualization-tools-for-your-marketing-reports) — MEDIUM confidence
- [Backfilling Data Pipelines: Best Practices — Medium](https://medium.com/@andymadson/backfilling-data-pipelines-concepts-examples-and-best-practices-19f7a6b20c82) — MEDIUM confidence
- PROJECT.md (this repo) — HIGH confidence (validated requirements)

---

---

## v1.0 Feature Research (Reference — Preserved from 2026-03-20)

This section is the original v1.0 feature research. It documents the v1.0 scope decisions and remains relevant as historical context.

### Table Stakes (v1.0)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Creative thumbnail / preview visible in dashboard | Users need to see the ad, not just a row of metrics | LOW | Assets already in GCS; thumbnail URLs already in CreativeAsset model |
| Performance metrics per creative (spend, ROAS, CTR, CPA, impressions) | Core reason the platform exists | LOW | HarmonizedPerformance already exists; surfacing is a UI concern |
| BrainSuite effectiveness score visible per creative | Primary missing piece; the whole point of this milestone | MEDIUM | POST to BrainSuite API, store result, surface in dashboard |
| Score dimension breakdown (not just aggregate score) | Agencies need "why" alongside "what" — which dimensions are weak/strong | MEDIUM | BrainSuite returns dimensions; need UI to render them meaningfully |
| Sorting creatives by score or by any performance metric | Users need to find top/bottom performers quickly | LOW | Backend sort/filter endpoint or frontend sort on loaded data |
| Date range filtering | Performance changes over time; agencies compare periods | LOW | Backend already accepts date range on dashboard stats |
| Cross-platform unified view | Agencies manage Meta + TikTok + Google simultaneously | LOW | Harmonization layer already built |
| Top performer / bottom performer identification | "Which creative do I scale? Which do I kill?" is the single most common question | LOW-MEDIUM | Can be derived from score + ROAS; needs visual treatment |
| Platform filter (see only Meta creatives, only TikTok, etc.) | Users want to compare within platform before cross-platform | LOW | Filter on platform field in HarmonizedPerformance |
| Sync status visibility | Users need to know if data is current or stale | LOW | Sync job model already exists; surface last sync timestamp |
| Reliable background sync with error surfacing | Silently stale data destroys trust | MEDIUM | APScheduler exists; error handling and user-visible error states needed |

### Differentiators (v1.0)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| BrainSuite score ALONGSIDE native platform metrics | Competitors (Motion, Superads) derive scores from performance data; BrainSuite uses pre-launch creative analysis — fundamentally different signal | LOW (integration) / MEDIUM (UX) | This is the core differentiator; needs clear UI treatment showing score is an independent signal, not derived from ROAS |
| Score-to-performance correlation view | Show creatives where high BrainSuite score predicted high ROAS — builds trust in the scoring system | MEDIUM | Requires scatter plot or table comparing score vs. ROAS; powerful for agency buy-in |
| Dimension-level weakness identification | "Your hook score is low" is actionable; a single number is not | MEDIUM | BrainSuite returns dimensions; render each dimension with label + value + simple indicator |
| Automatic scoring on sync (no manual trigger needed) | Friction-free; score is always present when the creative appears | MEDIUM | Queue scoring job after sync completes; handle API rate limits |
| Org-level scoring history | Track how BrainSuite scores change as creative iterations are uploaded | MEDIUM | Score stored with timestamp; trend view is a future feature |

### Anti-Features (v1.0)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time notifications (Slack, email when score arrives) | Agencies want to be alerted to new results | Out of scope for v1 per PROJECT.md; adds infrastructure complexity with low ROI when users are still onboarding | Show "unreviewed" badge on new scores; user polls dashboard |
| Ad copy / text creative scoring | Agencies want everything scored | Explicitly out of scope per PROJECT.md; text scoring is a different model | Images + video only in v1; extend in v2 |
| DCO (Dynamic Creative Optimization) suggestions | "Tell me what to change to improve my score" | Requires generative AI pipeline; far outside current scope | Surface score dimensions so creative teams draw their own conclusions |
| Competitor creative benchmarking | Agencies want to know if their score is good relative to market | Data not available | Score percentile within the user's own account |
| White-label / client-facing reports | Agencies want to share with clients | Adds multi-tier auth, branding customization, PDF/email generation | "Share link" to read-only view as a v1.5 feature |
| Mobile app | Agencies review on mobile | Web-first per PROJECT.md | Responsive Angular layout |

### Competitor Feature Analysis (v1.0)

| Feature | Motion | Superads | Our Approach |
|---------|--------|---------|--------------|
| Creative score | Derived from performance data | Percentile scores from perf data | BrainSuite pre-launch effectiveness score — independent AI signal |
| Score dimensions | AI-tagged creative elements | 5 performance-based signal dimensions | BrainSuite dimensions (attention, message clarity, visual quality, CTA) |
| Multi-platform | Meta, TikTok, YouTube | Meta, TikTok, LinkedIn, YouTube, Google Ads | Meta, TikTok, Google Ads, DV360 |
| Filtering | Per-platform, tags, date range | Fully customizable boards | Platform, date range, status |
| Multi-account | Yes | Yes | Yes — org-level multi-account (already built) |
| White label | Yes | Yes | Not in v1 |
| Key differentiator | Creative inspiration library | Fastest load times, customizable boards | Only platform combining BrainSuite pre-launch score WITH live performance data |

**Key competitive insight:** Motion and Superads derive scores from performance data — they tell you what already happened. BrainSuite scores the creative before (or independent of) performance. This is a genuinely different value proposition: use BrainSuite score to predict which creatives to run, then confirm with performance data. The UI should reinforce this distinction.

### Agency-Specific UX Expectations (v1.0)

1. **Speed of comprehension.** Agencies review dozens of creatives quickly. Score must be visible without clicking into detail.
2. **Actionable output, not data dumps.** Design for the decision, not the data.
3. **Percentile context helps.** If BrainSuite scores are absolute (0–100), add context: "above 70 = strong", or show relative position within account.
4. **Multi-account without friction.** Agencies log in once and need to switch between clients or see all at once.
5. **Trust requires transparency.** Agencies are skeptical of black-box scores. Showing dimension breakdown is essential for credibility.
