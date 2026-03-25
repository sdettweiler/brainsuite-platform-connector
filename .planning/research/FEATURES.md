# Feature Landscape

**Domain:** Creative analytics dashboard for ad agencies (performance marketing)
**Researched:** 2026-03-25 (v1.1 update; v1.0 research preserved below)
**Confidence:** MEDIUM–HIGH

---

## v1.1 Feature Research — Insights + Intelligence Milestone

This section covers the seven new capabilities being added: image scoring, AI metadata inference, score-to-ROAS correlation, top/bottom performer highlights, score trend over time, in-app notifications, and historical backfill scoring.

---

## Table Stakes (Users Expect These in v1.1)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| BrainSuite image scoring | Images are a primary ad format on every platform. Video-only scoring is a conspicuous gap; agencies immediately ask "why isn't my image scored?" | Medium | Different BrainSuite endpoint/payload from video — requires API discovery at phase start. Core parity requirement. |
| Top/bottom performer highlights | Every creative analytics tool (Triple Whale, Motion, Superads, Segwise) highlights best/worst creatives visually. Users scan grids, not tables. | Low | Badge or ribbon overlay on the creative card. Top-N by score or ROAS. Define N (e.g., top 10% or top 3 in current view). |
| Score-to-ROAS correlation view | Agencies need to validate that BrainSuite score actually predicts performance. Without this view the score is a black box and buy-in is fragile. | Medium | Scatter plot is the correct chart type (see deep dive). Requires min N creatives with both score and ROAS populated. |
| In-app notifications for sync/scoring | Agency users run batches and come back later. Knowing when sync completes or scoring finishes is expected in any async-workflow tool. | Low–Medium | Toast + bell icon inbox is the standard SPA pattern. In-app only for v1.1. |
| Historical backfill scoring | Assets synced before Phase 3 have no scores. Without backfill, the correlation and trend views are underpowered and users are confused by the missing data. | Medium | Idempotent batch job, rate-limited against BrainSuite API. One-time trigger (admin endpoint or UI). |

## Differentiators (Analytical Value Beyond Competitors)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| AI metadata auto-fill | Eliminates manual metadata entry before scoring. Agencies manage hundreds of creatives; filling 7 BrainSuite fields per asset is a real friction point that reduces scoring adoption. | High | Multi-modal: requires vision (image/video frame) + audio transcription (VO detection). See AI inference breakdown below. |
| Score trend over time | Shows whether creative effectiveness degrades as the creative fatigues in market. Lets agencies time creative retirement. VidMob and Segwise offer this; most simpler tools do not. | Medium | Requires multiple scoring runs per asset. The existing 15-min scheduler already creates data points on each run. |

## Anti-Features (Do Not Build in v1.1)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time WebSocket score updates | Scoring is batch (15-min scheduler). WebSockets add infrastructure complexity for zero user-visible benefit. | Polling (30s interval) for notification status is sufficient. |
| AI metadata fully replacing human input | LLM hallucination in production metadata is worse than blank fields. An incorrect Brand Name or Language silently corrupts the BrainSuite submission. | Surface inference as pre-populated suggestions with confidence indicators. Always allow override. Never auto-submit without user review. |
| Email/Slack notifications | Out of scope for v1.1 per PROJECT.md. Adds auth complexity and deliverability concerns. | In-app bell + toast only. Design the notification data model to allow external channels in v1.2 without a schema migration. |
| Per-platform correlation breakdown | Not enough data per-platform in early tenants to show meaningful separation. Cross-platform correlation is more useful at this stage. | One unified scatter plot. Platform filter as a secondary control. |
| Automated creative retirement based on score | Too prescriptive. Agencies have non-score reasons to keep assets running (brand campaigns, contracted placements). | Surface the data; let the user act. |

---

## Feature Deep Dives

### 1. AI Metadata Inference — Inferable vs Requires Human Input

**Context:** BrainSuite requires metadata fields alongside every asset submission. The 7 fields are: Language/Market, Brand Names, Project Name, Asset Name, Asset Stage, Voice Over (yes/no), Voice Over Language. This research assesses what Claude Vision + audio transcription can realistically infer.

#### Fields with Reliable AI Inference (HIGH confidence, surface as pre-filled)

| Field | How Inferred | Accuracy Expectation | Confidence |
|-------|--------------|----------------------|------------|
| Voice Over (yes/no) | Audio transcription of video detects speech vs music/silence. For images: always No — no inference needed. | ~95%. Binary detection is robust with modern audio models. | HIGH |
| Voice Over Language | Whisper-class audio model detects spoken language from audio waveform + transcript content. | ~90% on major languages (English, Spanish, French, German, Mandarin). Drops on regional dialects or heavily accented speech. Flag uncertain results. | MEDIUM–HIGH |
| Language/Market | Visible text in the creative (headline, CTA, overlay copy) — Claude Vision extracts text, language model classifies language and region. | ~90% when legible text is present. Unreliable for image-only creatives without text, or for market inferences beyond language (e.g., "US English" vs "UK English"). | MEDIUM |
| Asset Name | Derived from the filename or URL slug from the ad platform sync. Not true inference — normalization of existing structured data. Strip file extensions, replace underscores with spaces, title-case. | ~85% useful. Depends on agency naming conventions. | MEDIUM |

#### Fields Requiring AI Suggestion + Human Validation (MEDIUM confidence, surface as suggestions with review required)

| Field | What AI Can Suggest | Why Human Review Is Mandatory |
|-------|---------------------|-------------------------------|
| Brand Names | Claude Vision identifies logo text and prominent brand marks. Works well for major recognized brands. | Niche brands, sub-brands, and partnership creatives (two brand logos) are ambiguous or missed. Hallucination risk is high when the model is uncertain. Must be reviewable. |
| Asset Stage | Visual cues correlate loosely with funnel stage (product-only = awareness, price shown = conversion, testimonial = consideration). | Stage classification varies by agency convention. One agency's "awareness" is another's "retargeting." AI suggestion + dropdown correction is the right pattern. |

#### Fields That Cannot Be Reliably Inferred (require manual entry)

| Field | Why Not Inferable |
|-------|------------------|
| Project Name | A project is an organizational construct inside the agency — it does not appear in creative content. Can sometimes be parsed from ad account campaign names if those are well-structured, but this is too fragile to rely on. Best pattern: inherit from a campaign-level default or require manual entry once per project. |

#### UX Implementation Pattern

Use a two-phase interaction: (1) inference runs async when user selects a creative for scoring (trigger on modal open); (2) pre-populated form is shown with per-field confidence indicators; (3) user reviews, corrects if needed, and explicitly submits. Never auto-submit AI-filled fields to BrainSuite without user confirmation.

**Confidence indicator design:** A subtle visual state on each field — solid fill/green border for high confidence (VO detection), muted/amber for medium (language, brand), empty/dashed border for uninferable (Project Name). This communicates reliability without creating anxiety.

**Latency budget:** Claude Sonnet-class inference on a ~1MB image takes 2–5 seconds. For video, add audio extraction: ~1–3 seconds for a 30-second clip processed by a transcription model. Total expected latency: 5–10 seconds per asset. This is acceptable if triggered async on modal open, not on page load.

**Cost note (Claude Vision):** A 1-megapixel image uses ~1,334 tokens at $3/million input tokens = ~$0.004 per image. At 1,000 creatives, inference costs ~$4.00 in API fees. Acceptable for this use case. Video adds audio transcription overhead (Whisper API ~$0.006/minute of audio).

**Critical edge case:** If the creative has no legible text (all visual, no copy), Language/Market inference returns no signal. The field should remain blank, not hallucinated. The confidence indicator must show "empty/manual required" in this case.

---

### 2. Score-to-ROAS Correlation — Chart Type and Data Requirements

**Recommended chart type: Scatter plot with quadrant reference lines.** One dot per creative. X-axis = BrainSuite effectiveness score (0–100). Y-axis = ROAS. Reference lines at median score and median ROAS create four quadrants:

- **Stars** (high score, high ROAS): Scale budget here.
- **Question Marks** (high score, low ROAS): Score predicts quality — investigate audience/targeting or wait for data maturity.
- **Workhorses** (low score, high ROAS): Distribution is carrying this creative — may not sustain.
- **Laggards** (low score, low ROAS): Kill or iterate.

This quadrant framing is the most actionable output of the correlation view. It answers "what do I do?" rather than just "what is the relationship?". Segwise, VidMob, and Madgicx all use this type of two-variable creative intelligence view.

**Data requirements:**

| Requirement | Minimum Threshold | Notes |
|-------------|-------------------|-------|
| Creatives with both score AND ROAS | 10+ for a visible pattern; 30+ for meaningful statistical signal | Below 10 points: show an empty-state with "Score more creatives to see correlation" + CTA to run backfill |
| ROAS data | Already synced in v1.0 normalized metrics | No new backend work needed |
| Score data | BrainSuite scoring pipeline (v1.0) + image scoring (v1.1) + historical backfill | Backfill is a dependency for a useful chart on day one |
| Currency normalization | Already handled in v1.0 | No new work |

**Edge cases to handle:**

| Edge Case | Handling |
|-----------|---------|
| Creatives with spend = 0 / ROAS = 0 | Exclude from scatter plot. Show count of excluded creatives ("12 creatives excluded — no spend data"). |
| ROAS outliers (viral one-off, extremely high ROAS) | Cap Y-axis at 99th percentile by default. Provide a log-scale toggle or "show all" option. Clipping prevents one outlier from flattening the rest of the chart. |
| Image vs. video in the same chart | Color-code dots by creative type (image = one color, video = another). Legend toggle to isolate by type. |
| Same creative on multiple platforms with different ROAS | In v1.1: use average ROAS across all placements for the dot. Surface per-platform breakdown in the hover tooltip. |
| Creatives with score but no ROAS | Show dot on X-axis with a distinct style (hollow or striped). Label axis region "No performance data yet." |

**Hover tooltip:** Thumbnail, asset name, score, ROAS, platform(s), total spend. This replaces the need for a click-to-detail flow from the scatter plot.

**Empty state trigger:** If fewer than 10 data points exist (both score + ROAS populated), show the chart skeleton with message and a "Run historical backfill" CTA — links the two features together in the UI.

---

### 3. In-App Notifications — Delivery Mechanism

**Standard pattern for ad tech dashboards: Toast (ephemeral) + bell icon inbox (persistent history).**

Toasts serve current-session events (user is looking at the app). The bell inbox serves users who were away — they return and see what happened while they were gone. These two components serve different needs; both are required.

**Events to surface:**

| Event | Toast | Bell Inbox | Severity |
|-------|-------|------------|----------|
| Sync completed (platform X, N creatives synced) | Yes (auto-dismiss 5s) | Yes | Normal |
| Sync failed (platform X, error reason) | Yes (persistent — dismiss required) | Yes | High |
| Scoring batch completed (N assets scored) | Yes (auto-dismiss 5s) | Yes | Normal |
| Token expiry imminent (72h warning) | Yes (on login) | Yes | High |
| Token expired / connection lost | Yes (every session until reconnected) | Yes | High |

**Transport recommendation: HTTP polling at 30-second intervals.** Do not build SSE or WebSockets for v1.1.

Rationale: SSE (Server-Sent Events) on FastAPI is possible via `sse-starlette` but adds a persistent connection per user that competes with the existing background scheduler on a single-process deployment. The notification events in scope (sync complete, scoring complete, token expiry) happen at minute-to-hour granularity — 30-second polling latency is invisible to users. Polling survives proxy timeouts, load balancer idle disconnects, and Docker network resets without reconnect logic.

Migrate to SSE in v1.2 if real-time notification latency becomes a user complaint. The notification data model designed here supports both polling and SSE without schema changes.

**Backend data model:** Add a `notifications` table: `(id, org_id, user_id nullable, event_type, title, body, severity, created_at, read_at nullable)`. `user_id` is nullable to support org-wide notifications (e.g., token expiry affects all org users). Polling endpoint: `GET /api/notifications?unread=true`. Mark-read: `PATCH /api/notifications/{id}/read`. Bulk-read: `PATCH /api/notifications/read-all`.

**Bell badge:** Show count of unread high-severity notifications as a red badge. Cap display at 99+. Normal-severity unread notifications use a dot indicator, not a number. Clear the count when the inbox panel is opened, not on individual item read (this is the Gmail/Slack pattern).

**Toast library recommendation:** `ngx-toastr` (well-maintained, Angular 17 compatible, customizable) or Angular Material Snackbar (already in the Material bundle if the project uses Angular Material). Use `aria-live="polite"` on the toast container for screen reader accessibility. High-severity toasts (sync failed, token expired) should require explicit dismiss, not auto-dismiss.

**Notification hook points in the codebase:** The scoring scheduler and sync jobs in FastAPI need to write notification records on completion/failure. Add a `NotificationService` helper that writes to the notifications table — call it at the end of each job's success and error paths.

---

### 4. Score Trend Over Time — Time Window and Data Density

**What constitutes a data point:** Each time the 15-minute scheduler runs BrainSuite scoring for an asset and receives a score, that is one data point in the trend series. The trend line is a per-asset time series of consecutive BrainSuite scoring results stored with timestamps.

**The data density problem:** BrainSuite scoring is scheduler-triggered — not triggered by real-world creative changes. In early deployment, a creative may have only one or two score records (initial scoring + one re-run). The trend view is only useful once an asset has 3+ data points spread across multiple days.

**Recommended time window: 30 days rolling.** Industry standard for creative fatigue analysis — Triple Whale, Supermetrics, and Madgicx all use 7-day and 30-day windows as the primary analytical frames. Display individual data points as dots on the line (do not smooth/interpolate). Users need to see actual score values, not a smoothed curve that hides score variance.

**Expected data density by deployment scenario:**

| Scenario | Data Points in 30 Days | Chart Usefulness |
|----------|------------------------|-----------------|
| Scheduler scores active assets on every run | Multiple per week | High — trend and fatigue signals visible |
| Assets scored once per day (manual or less active scheduler) | ~30 data points | Good — clean trend line |
| Assets scored once per week | ~4 data points | Minimal but visible trend |
| Asset scored once (initial only, scheduler not re-triggering) | 1 point | Do not render as a line chart — show single score value with note |

**Empty state rule:** A single data point must not render as a line chart. Show the score as a standalone metric with copy: "Score history requires multiple scoring runs. Rescore this creative to begin tracking trend."

**Minimum useful chart: 2 data points.** Even with 2 points a direction (improving/declining) is visible. Use a single connected line with two dots, no smoothing.

**Chart placement:** Render in the asset detail panel/dialog, as a tab alongside the existing CE dimension breakdown. Label the tab "Score History." The score badge in the grid always shows the most recent score — the trend is a drill-down.

**Y-axis: always fixed at 0–100.** Never auto-scale. A score moving from 62 to 65 on an auto-scaled axis looks dramatic; on a fixed axis it is correctly read as a small improvement. Absolute score magnitude matters as much as direction.

**Creative fatigue signal:** If the most recent 7-day average score is more than 10 points below the 30-day peak score, surface a "Possible fatigue" indicator (icon + label) on the trend chart. This is a simple threshold rule, not a ML model. Agencies recognize this pattern from tools like Supermetrics.

**Time-axis granularity:** Label X-axis with dates, not run numbers. If multiple scoring runs happen in the same day, show all data points — do not collapse to daily average. The exact timestamp in the tooltip helps users correlate score changes with creative edits or campaign changes.

---

## Feature Dependencies

```
BrainSuite image scoring
    ──enables──> AI metadata inference (images need the scoring flow to be triggered)
    ──enables──> Score-to-ROAS correlation (more assets with scores)
    ──enables──> Score trend over time (more assets with history)

AI metadata inference
    ──requires──> BrainSuite image scoring flow (metadata submitted alongside scoring request)
    ──requires──> Claude API key configured (ANTHROPIC_API_KEY in env)

Historical backfill scoring
    ──populates──> Score-to-ROAS correlation (correlation needs data to be useful)
    ──populates──> Score trend over time (trend needs multiple data points)
    ──requires──> BrainSuite video scoring (already exists in v1.0)
    ──requires──> BrainSuite image scoring (v1.1 — backfill should cover both types)

Score-to-ROAS correlation
    ──requires──> Score data (v1.0 scoring pipeline + image scoring + backfill)
    ──requires──> ROAS data (already in v1.0 harmonized metrics)

Score trend over time
    ──requires──> Multiple scoring runs per asset (scheduler already runs; backfill accelerates)
    ──enhances with──> Historical backfill (more historical data points)

Top/bottom performer highlights
    ──requires──> Score data (already in v1.0 for video; image scoring extends coverage)
    ──requires──> ROAS data (already in v1.0)
    ──no new dependencies beyond existing v1.0 data

In-app notifications
    ──requires──> Notification table + API endpoints (new)
    ──hooks into──> Sync jobs (already exist — add notification write on complete/fail)
    ──hooks into──> Scoring scheduler (already exists — add notification write on batch complete)
    ──no dependency on other v1.1 features
```

**Critical path for correlation view being useful on day one:**

1. Historical backfill must run (or be triggered immediately after deployment)
2. Image scoring must be wired up (significantly expands the scored asset pool)
3. Then the scatter plot has enough data to show a pattern

---

## MVP Sequencing for v1.1

**Wave 1 — prerequisites and data foundation (build first):**
1. BrainSuite image scoring — parity feature, also unlocks image data for all insight features
2. Historical backfill scoring — populates data for correlation and trend views; run as soon as deployed
3. In-app notifications — standalone deliverable, lower complexity, high perceived value

**Wave 2 — insight features (build after Wave 1 data foundation):**
4. AI metadata auto-fill — depends on image scoring being wired up
5. Score-to-ROAS correlation — scatter plot; best with backfill data
6. Top/bottom performer highlights — simple overlay on existing grid
7. Score trend over time — per-asset; only meaningful with multiple scoring runs

**Rationale for this order:** The insight features (correlation, trend, performer highlights) are only compelling if they have enough data. Shipping them before backfill runs results in empty states and weak first impressions. Backfill + image scoring first means the insight features arrive with data already in them.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| AI metadata inference field-by-field breakdown | MEDIUM | Claude Vision capabilities verified via official Anthropic docs. Field-specific accuracy estimates are based on known VLM capabilities, not BrainSuite-specific testing. Actual accuracy will depend on creative quality and ad platform conventions. |
| Scatter plot as correct chart for correlation | HIGH | Industry consensus: Segwise, VidMob, Madgicx, and Improvado all use scatter/two-variable correlation for creative analytics. |
| Polling over SSE for notifications | HIGH | Architecture rationale is sound for the existing FastAPI + Docker Compose stack. SSE is technically viable but the complexity/benefit ratio is poor for this notification frequency. |
| 30-day trend window | HIGH | Industry consensus from Supermetrics, Triple Whale, Madgicx — 7/30-day windows are universal. |
| Backfill as dependency for insight feature usefulness | HIGH | Logical dependency, not a research claim requiring validation. |
| AI inference latency (5–10s) | MEDIUM | Estimated from Claude API performance benchmarks for vision tasks. Actual latency depends on asset dimensions, API load, and audio extraction approach. |
| Top/bottom performer highlight complexity (Low) | HIGH | This is purely a frontend concern — the data already exists. Badge/ribbon overlay on existing creative cards. |

---

## Sources

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
