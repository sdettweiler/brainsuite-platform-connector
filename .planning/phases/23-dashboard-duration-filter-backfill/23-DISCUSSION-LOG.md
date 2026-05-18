# Phase 23: Dashboard Duration Filter + Backfill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 23-dashboard-duration-filter-backfill
**Areas discussed:** Slider bounds, Slider visibility, NULL callout, Backfill trigger

---

## Slider bounds

### Q1: How should the duration slider's min/max range be determined?

| Option | Description | Selected |
|--------|-------------|----------|
| Dynamic from API | GET /dashboard/duration-bounds returns actual min/max from org | ✓ |
| Fixed 0–300s | Hardcoded ceiling — simpler, no extra endpoint | |
| Fixed 0–600s | More generous ceiling | |

**User's choice:** Dynamic from API

---

### Q2: Bounds scope — org-wide or filter-aware?

| Option | Description | Selected |
|--------|-------------|----------|
| Org-wide bounds | One call on load, cached; stable range | |
| Filter-aware bounds | Recomputes when other filters change; matches visible data | ✓ |

**User's choice:** Filter-aware bounds

---

### Q3: Slider label format

| Option | Description | Selected |
|--------|-------------|----------|
| Formatted (e.g. 0s – 2m 15s) | formatDuration() helper — human-readable | ✓ |
| Raw seconds (e.g. 0 – 135s) | Simpler, consistent with score range | |

**User's choice:** Formatted

---

## Slider visibility

### Q1: When no VIDEO assets in grid

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden completely | Doesn't appear when hasVideoAssets = false | ✓ |
| Visible but disabled with tooltip | Score slider pattern — disabled + tooltip | |

**User's choice:** Hidden completely

---

### Q2: What counts as a video asset?

| Option | Description | Selected |
|--------|-------------|----------|
| asset_type == 'video' in API response | Check API response field | ✓ |
| Any asset with video_url set | More permissive | |
| You decide | Planner picks | |

**User's choice:** asset_type == 'video'

---

## NULL callout

### Q1: When does the callout appear?

| Option | Description | Selected |
|--------|-------------|----------|
| Only when duration filter is active | Contextually relevant | ✓ |
| Always (when slider is visible) | Proactively informs | |

**User's choice:** Only when duration filter is active

---

### Q2: What does X represent?

| Option | Description | Selected |
|--------|-------------|----------|
| Count within current filter state | Dynamic — matches other active filters | ✓ |
| Total org count | Static — simpler but potentially misleading | |

**User's choice:** Count within current filter state

---

### Q3: Where does the callout render?

| Option | Description | Selected |
|--------|-------------|----------|
| Below the chip row (inline) | Near the filter, low visual noise | ✓ |
| Info banner above the grid | More prominent | |

**User's choice:** Below the chip row

---

## Backfill trigger

### Q1: What triggers the backfill?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual button in SuperAdmin | Explicit — fits existing admin action pattern | |
| Auto on startup if NULLs exist | Scheduler-driven — no admin action needed | |
| After each sync run | Automatic; triggered when new NULLs created | ✓ |

**User's choice:** After each sync run

---

### Q2: Which assets does the backfill target?

| Option | Description | Selected |
|--------|-------------|----------|
| All platforms where video file is local | Covers DV360, Google Ads, TikTok, Meta | ✓ |
| DV360 + Google Ads only | Safer, proven; leaves other platforms with NULLs | |

**User's choice:** All platforms where video file is local

---

### Q3: Batch behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Batch of 100, sequential | CPU-bound ffprobe; sequential avoids spike | ✓ |
| Batch of 50, sequential | Lighter per-run | |
| You decide | Planner picks based on asset count | |

**User's choice:** Batch of 100, sequential

---

## Claude's Discretion

- Debounce timing for filter-aware bounds refresh — planner decides appropriate debounce window
- Whether to extract `_get_video_duration()` to a shared `video_utils.py` or inline in backfill service — planner decides

## Deferred Ideas

- Filter state URL persistence (duration_min/max in query params) — v1.5, explicitly Out of Scope
- Saved filter presets — REQUIREMENTS.md Out of Scope
- Duration histogram overlay on slider — nice-to-have, not in ROADMAP scope
