# Phase 7: Score Trend, Performer Highlights + Performance Tab - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 07-score-trend-performer-highlights-performance-tab
**Areas discussed:** Score Trend chart, Performer Badges, Performance Tab Redesign, Score History Write Logic

---

## Score Trend Chart

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 30-day window | No controls | |
| Toggle: 7 / 30 / 90 days | Three preset buttons | |
| Free date range picker | Reuse DateRangePickerComponent | ✓ |

**User's choice:** Free date range picker using existing DateRangePickerComponent

---

| Option | Description | Selected |
|--------|-------------|----------|
| "Not enough data yet" | Generic, honest | ✓ |
| "Score history starts building after first scoring run" | More explanatory | |
| You decide | Claude picks copy | |

**User's choice:** "Not enough data yet"

---

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse DateRangePickerComponent | Consistent, already in dialog | ✓ |
| Standalone date inputs | Two mat-datepicker fields | |

**User's choice:** Reuse DateRangePickerComponent

---

| Option | Description | Selected |
|--------|-------------|----------|
| Line + dots | Clean, precise, each point hoverable | ✓ |
| Smooth area fill | Softer visual with orange fill | |
| You decide | Claude picks | |

**User's choice:** Line + dots

---

**Critical pivot discovered during discussion:**
User clarified that asset-level scores are static (confirmed D-09 Phase 5). The top-left "chart" in their Performance tab design referred to the existing KPI trend chart, not a score trend chart. Score trends are only meaningful at aggregate/portfolio level, not per asset.

---

## Performer Badges

| Option | Description | Selected |
|--------|-------------|----------|
| Top-left corner | Most visible, near format overlay | |
| Bottom-left corner | Separate from score badge (bottom-right) | ✓ |
| You decide | Claude picks least cluttered spot | |

**User's choice:** Bottom-left corner

---

| Option | Description | Selected |
|--------|-------------|----------|
| Small colored pill/chip | ⬆ Top / ⬇ Bottom in green/red | ✓ |
| Icon only | Star/arrow with tooltip | |
| Text tag (tile-tag style) | Reuse existing .tile-tag | |

**User's choice:** Small colored pill/chip

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep labels, change logic | "Top Performer" / "Below Average" labels; switch to PERCENT_RANK() | ✓ |
| New labels: Top 10% / Bottom 10% | More explicit pill text | |
| You decide | Claude picks | |

**User's choice:** Keep existing labels, replace threshold logic with PERCENT_RANK()

---

## Score Trend — Re-scope Decision

| Option | Description | Selected |
|--------|-------------|----------|
| Drop TREND-02 + TREND-03 | Mark as deferred/invalidated | |
| Re-scope: aggregate score trend in dashboard | Portfolio-level avg score over time | ✓ |
| Defer to future phase | Revisit if scoring changes | |

**User's choice:** Re-scope to aggregate score trend panel in main dashboard

---

| Option | Description | Selected |
|--------|-------------|----------|
| New dashboard panel above grid | Dedicated chart panel, visible without dialog | ✓ |
| Stats bar expansion | Extend existing header stats | |
| You decide | Claude picks placement | |

**User's choice:** New dashboard panel/card above the creative grid

---

| Option | Description | Selected |
|--------|-------------|----------|
| 30-day default with date range picker | Reuse DateRangePickerComponent | ✓ |
| Fixed 30-day rolling window | No controls | |
| 7 / 30 / 90 day toggle | Preset buttons | |

**User's choice:** 30-day default with DateRangePickerComponent

---

## Performance Tab Redesign

**User's custom layout specification (free-text):**
> "1 tile for the chart top left, one aligned tile top right with the creative asset. Within the creative asset tile have the filename underneath (left aligned) and if it's a video the length in the same line right aligned. Spend and Impressions as smaller data tiles underneath, but within the creative asset tile. Above the creative asset have 'Creative Asset' as headline (top left inside the tile) and the Rank badge top right.
> Underneath have full width metrics section (Performance Summary). Each row is grouped by the Metric Category (color coded with leading icons) with the actual metrics right of it.
> At the bottom of the page we'll have the 'Used in X campaigns' tile, listing all campaigns. Each row representing one campaign should contain a link icon linking out to the campaign at the publisher in a new tab/window.
> Design is aligned with the CE Tab."

---

| Option | Description | Selected |
|--------|-------------|----------|
| Keep KPI selector | Multi-select checkboxes for Spend/CTR/ROAS | ✓ |
| Show top 3 metrics only | Fixed Spend + CTR + ROAS | |
| You decide | Claude decides | |

**User's choice:** Keep existing KPI selector in the chart tile

---

| Option | Description | Selected |
|--------|-------------|----------|
| You decide (Claude groups) | Delivery, Engagement, Conversions, Video, Platform-specific | ✓ |
| I'll specify categories | User provides groupings | |

**User's notes:** Delivery, Engagement, Conversions, Video, Platform-specific. Claude makes recommendations for orphan metrics.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, build link from URL patterns | Construct from campaign_id + platform | ✓ |
| No link — show name only | No external link | |
| I'll provide URL patterns | User specifies | |

**User's choice:** Build campaign URL from known patterns per platform

---

## Score History Write Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Add creative_score_history table + daily snapshot | New table, append per COMPLETE result | |
| Compute on-the-fly from CreativeScoreResult | Use scored_at + total_score, no new table | ✓ |
| You decide | Claude picks | |

**User's choice:** Compute on-the-fly — no new table. AVG(total_score) GROUP BY day from existing CreativeScoreResult.scored_at.

**User's clarification:** "we do not add a new table.. compute on the fly"

---

*Discussion completed: 2026-03-30*
