# Feature Research

**Domain:** Creative analytics / ad performance platform with AI effectiveness scoring
**Researched:** 2026-03-20
**Confidence:** MEDIUM-HIGH (primary competitors verified via official sources; some specifics extrapolated from market context)

---

## Context: What This Product Is

A multi-tenant SaaS for agencies and advertisers that syncs creatives from Meta, TikTok, Google Ads, and DV360, displays harmonized performance metrics, and enriches each creative with a BrainSuite effectiveness score + dimension breakdown. The core value proposition: see every creative's performance AND its BrainSuite score in one place — instantly know what to scale or kill.

This is a **subsequent milestone** — the platform connector already exists. The gap being closed is BrainSuite integration + production hardening + dashboard polish.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing = product feels broken or untrustworthy.

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

### Differentiators (Competitive Advantage)

Features that go beyond table stakes. These are where BrainSuite Platform Connector competes.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| BrainSuite score ALONGSIDE native platform metrics | Competitors (Motion, Superads) derive scores from performance data; BrainSuite uses pre-launch creative analysis — fundamentally different signal | LOW (integration) / MEDIUM (UX) | This is the core differentiator; needs clear UI treatment showing score is an independent signal, not derived from ROAS |
| Score-to-performance correlation view | Show creatives where high BrainSuite score predicted high ROAS — builds trust in the scoring system | MEDIUM | Requires scatter plot or table comparing score vs. ROAS; powerful for agency buy-in |
| Dimension-level weakness identification | "Your hook score is low" is actionable; a single number is not | MEDIUM | BrainSuite returns dimensions; render each dimension with label + value + simple indicator |
| Multi-platform creative identity (same creative on Meta and TikTok) | Agencies repurpose creatives; seeing one creative's score across platforms is unique | HIGH | Requires asset deduplication or user-managed grouping; defer unless BrainSuite requires it |
| Automatic scoring on sync (no manual trigger needed) | Friction-free; score is always present when the creative appears | MEDIUM | Queue scoring job after sync completes; handle API rate limits |
| Org-level scoring history | Track how BrainSuite scores change as creative iterations are uploaded | MEDIUM | Score stored with timestamp; trend view is a future feature |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable but create more problems than they solve at this stage.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time notifications (Slack, email when score arrives) | Agencies want to be alerted to new results | Out of scope for v1 per PROJECT.md; adds infrastructure complexity (queuing, delivery guarantees, opt-in management) with low ROI when users are still onboarding | Show "unreviewed" badge on new scores; user polls dashboard |
| Ad copy / text creative scoring | Agencies want everything scored | Explicitly out of scope per PROJECT.md; BrainSuite schema TBD; text scoring is a different model | Images + video only in v1; extend in v2 |
| DCO (Dynamic Creative Optimization) suggestions | "Tell me what to change to improve my score" | Requires generative AI pipeline; far outside current scope; risks making incorrect creative guidance | Surface score dimensions so creative teams draw their own conclusions |
| Competitor creative benchmarking | Agencies want to know if their score is good relative to market | Data not available; would require industry dataset BrainSuite doesn't provide | Score percentile within the user's own account (relative to their portfolio) |
| White-label / client-facing reports | Agencies want to share with clients | Adds multi-tier auth, branding customization, PDF/email generation — significant scope; not validated need for v1 | "Share link" to read-only view as a v1.5 feature |
| Audience / targeting asset import | Agencies assume "all assets" means everything | Out of scope per PROJECT.md; audiences and targeting data are structurally different from creative assets | Explicit messaging in UI that only image/video creatives are scored |
| Mobile app | Agencies review on mobile | Web-first per PROJECT.md; responsive design covers mobile browsers adequately | Responsive Angular layout |
| Real-time sync (sub-minute) | "Why isn't my new ad showing up?" | Platform APIs rate-limit and batch data; real-time is technically impossible for most ad platforms | Clear "sync runs daily at X time" messaging; manual sync trigger button |

---

## Feature Dependencies

```
[BrainSuite Score Display]
    └──requires──> [BrainSuite API Integration (POST asset, receive score)]
                       └──requires──> [Creative Asset in GCS with accessible URL]
                                          └──requires──> [Platform Sync (already built)]

[Score Dimension Breakdown UI]
    └──requires──> [BrainSuite API Integration]
    └──requires──> [Score stored with dimensions in DB]

[Top/Bottom Performer Identification]
    └──requires──> [Score Display]
    └──enhances──> [Performance Metrics per Creative]

[Sort by Score or Metric]
    └──requires──> [Score stored in DB]
    └──requires──> [Performance Metrics per Creative]

[Date Range Filtering]
    └──requires──> [Performance Metrics per Creative]
    └──enhances──> [Top/Bottom Performer Identification]

[Score-to-Performance Correlation View]
    └──requires──> [BrainSuite Score stored]
    └──requires──> [Performance Metrics per Creative]
    (defer to v1.x)

[Auto-Scoring on Sync]
    └──requires──> [BrainSuite API Integration]
    └──requires──> [Sync completion event / hook]

[Sync Status Visibility]
    └──requires──> [Sync Job model (already built)]

[Production Security]
    ──blocks──> [External user onboarding]
    (OAuth session fix + JWT storage must land before real users)
```

### Dependency Notes

- **Score display requires API integration:** The BrainSuite schema (exact fields, score structure, dimension names) must be validated from BrainSuite docs before UI can be finalized. Build API integration first, inspect real responses, then design UI.
- **Auto-scoring requires a trigger point:** The cleanest approach is to enqueue scoring after sync marks an asset as new. APScheduler or a post-sync hook works; do not require manual user trigger.
- **Production security is a gate, not a feature:** The in-memory OAuth session store and localStorage JWT issue are blockers for any real user onboarding. These must be resolved before the scoring features are exposed externally.
- **Performance metrics + score are independent signals:** BrainSuite scores creatives on predicted effectiveness, not measured performance. The UI must not imply the score is derived from ROAS/CTR. This is a UX discipline concern, not a data concern.

---

## MVP Definition

### Launch With (v1)

Minimum feature set for internal-first validation before external agency onboarding.

- [ ] BrainSuite API integration — POST asset URL + metadata, receive score + dimensions, persist to DB
- [ ] Auto-scoring on sync — new assets scored automatically without user action
- [ ] Score + dimension breakdown visible in creative list/detail — score prominent, dimensions labeled and readable
- [ ] Sort by score, ROAS, spend, CTR — users find top/bottom performers by any signal
- [ ] Platform filter + date range filter — narrow view to relevant subset
- [ ] Creative thumbnail visible — users see the ad, not just data
- [ ] Sync status display — last synced timestamp per platform connection
- [ ] Production security hardening — replace in-memory OAuth sessions, move JWT to httpOnly cookies
- [ ] Sync error surfacing — failed syncs visible in UI, not silently dropped

### Add After Validation (v1.x)

Add when initial users confirm value and identify friction.

- [ ] Score-to-performance correlation view — scatter/table of BrainSuite score vs. ROAS, validates scoring value to skeptical agencies
- [ ] Manual re-score trigger — for assets where score is missing or stale
- [ ] Read-only share link for creative reports — enables agencies to share results without giving client full platform access
- [ ] Period-over-period performance comparison — already partially built in dashboard stats; polish and surface

### Future Consideration (v2+)

Defer until product-market fit is established.

- [ ] White-label reports — only needed if agencies want client-facing output; validate demand first
- [ ] Notification system — useful, but polling dashboard works for early users
- [ ] Multi-platform creative identity (same creative across platforms) — high complexity, low validated demand
- [ ] Creative scoring trend over time (same creative re-scored after iteration) — requires iteration tracking; interesting but not urgent
- [ ] Ad copy / text creative scoring — scope expansion requiring BrainSuite capability validation

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| BrainSuite API integration (backend) | HIGH | MEDIUM | P1 |
| Score visible in dashboard | HIGH | LOW | P1 |
| Score dimension breakdown | HIGH | MEDIUM | P1 |
| Production security hardening (OAuth sessions, JWT) | HIGH (gate) | MEDIUM | P1 |
| Auto-scoring on sync | HIGH | MEDIUM | P1 |
| Sort/filter by score or metric | HIGH | LOW | P1 |
| Creative thumbnail visible | HIGH | LOW | P1 |
| Sync error surfacing | MEDIUM | LOW | P1 |
| Sync status display | MEDIUM | LOW | P1 |
| Top/bottom performer highlight | MEDIUM | LOW | P2 |
| Score-to-ROAS correlation view | MEDIUM | MEDIUM | P2 |
| Manual re-score trigger | MEDIUM | LOW | P2 |
| Read-only share link | MEDIUM | MEDIUM | P2 |
| White-label reports | LOW (v1) | HIGH | P3 |
| Notification system | LOW (v1) | HIGH | P3 |
| Text creative scoring | LOW (v1) | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Motion | Superads | Our Approach |
|---------|--------|---------|--------------|
| Creative score | Derived from performance data (not pre-launch) | Percentile scores from perf data (Click, Engagement, Hook, Hold, Conversion) | BrainSuite pre-launch effectiveness score — independent AI signal, not derived from ad spend |
| Score dimensions | AI-tagged creative elements (hooks, colors, CTAs) | 5 performance-based signal dimensions (Click, Hook, Hold, Engagement, Conversion) | BrainSuite dimensions (exact schema TBD) — likely attention, message clarity, visual quality, CTA |
| Multi-platform | Meta, TikTok, YouTube | Meta, TikTok, LinkedIn, YouTube, Google Ads | Meta, TikTok, Google Ads, DV360 |
| Filtering | Per-platform, tags, date range | Fully customizable boards | Platform, date range, status (v1); more in v1.x |
| Top performer ID | Visual board with sorted cards | Sortable tables, color-coded scores | Sort by score or ROAS; highlight extremes |
| Multi-account | Yes, core agency feature | Yes, cross-account unified view | Yes, org-level multi-account (already built) |
| White label | Yes | Yes | Not in v1 |
| Sharing | Report sharing | Interactive shareable boards | Read-only share link in v1.x |
| Key differentiator | Creative inspiration library + structured report types | Fastest load times, customizable boards, AI copilot | Only platform combining BrainSuite pre-launch score WITH live performance data in one view |

**Key competitive insight:** Motion and Superads derive scores from performance data — they tell you what already happened. BrainSuite scores the creative before (or independent of) performance. This is a genuinely different value proposition: use BrainSuite score to predict which creatives to run, then confirm with performance data. The UI should reinforce this distinction.

---

## Agency-Specific UX Expectations

Based on competitor research and agency workflow patterns:

1. **Speed of comprehension.** Agencies review dozens of creatives quickly. Score must be visible without clicking into detail. Superads loads in 2-3 seconds; anything slower feels broken.

2. **Actionable output, not data dumps.** "Creative X: BrainSuite score 82, ROAS 4.2x — scale it" is the desired mental output. Design for the decision, not the data.

3. **Percentile context helps.** Superads found users needed "is 60 good?" answered. If BrainSuite scores are absolute (0-100), add context: "above 70 = strong", or show relative position within account.

4. **Multi-account without friction.** Agencies log in once and need to switch between clients or see all at once. Organization structure already handles this; ensure the UI makes it obvious.

5. **Shared reports matter more than real-time.** Agencies share results with clients via decks/links, not live dashboards. A shareable URL is higher value than Slack notifications.

6. **Trust requires transparency.** Agencies are skeptical of black-box scores. Showing dimension breakdown (not just aggregate score) is essential for credibility. "Your score is 62 because hook score is 45" is trusted; "your score is 62" is not.

---

## Sources

- [Superads: How We Built Superads Scores](https://www.superads.ai/blog/how-we-built-superads-scores) — MEDIUM confidence (official Superads content)
- [Superads vs. Motion Feature Comparison](https://www.superads.ai/superads-vs-motion) — MEDIUM confidence (Superads marketing, but feature list verified)
- [Motion: Key Creative Performance Metrics](https://motionapp.com/blog/key-creative-performance-metrics) — MEDIUM confidence (official Motion content)
- [Segwise: Creative Analytics for Meta Ads in 2026](https://segwise.ai/blog/facebook-ads-reporting-creative-intelligence) — LOW-MEDIUM confidence (industry blog)
- [Segwise: 7 Best Ad Reporting & Creative Analytics Tools for UA](https://segwise.ai/blog/ad-reporting-tools-2026) — LOW-MEDIUM confidence (industry blog)
- [Madgicx: 10 Best Ad Tech Platforms for Creative Optimization in 2025](https://madgicx.com/blog/ad-tech-platform-for-creative-optimization) — LOW-MEDIUM confidence (industry blog)
- [Coupler.io: How to Track Performance of Ad Creatives](https://blog.coupler.io/how-to-track-performance-of-ad-creatives/) — LOW confidence (unverified)
- PROJECT.md (this repo) — HIGH confidence (validated requirements from project owner)

---

*Feature research for: BrainSuite Platform Connector — creative analytics / ad performance with AI scoring*
*Researched: 2026-03-20*
