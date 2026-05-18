# Phase 25: Configurable Concurrency - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 25-configurable-concurrency
**Areas discussed:** Semaphore scope, Update timing, Admin UI placement, Number input UX

---

## Semaphore Scope

### Q1: When DV360 and Google Ads sync run simultaneously, what does the limit mean?

| Option | Description | Selected |
|--------|-------------|----------|
| 3 total across both platforms | One shared semaphore — DV360 + Google Ads compete for the same N slots. Most download-bandwidth-friendly. This is what the requirement says: "shared asyncio semaphore." | ✓ |
| 3 per platform | Two separate semaphores — each platform gets its own N slots independently. Effectively doubles the limit when both run together. | |

**User's choice:** 3 total across both platforms  
**Notes:** Confirmed: one global semaphore, not per-platform.

### Q2: Where should the semaphore module live?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend proxy_cache.py | Phase 24 context already flagged this. Reuses module-level cache + asyncio.Lock pattern already tested by 7 unit tests. | ✓ |
| New module: download_semaphore.py | Clean separation of concerns. Slightly more files but each does one thing. | |
| You decide | Let the planner choose based on what's most idiomatic. | |

**User's choice:** Extend proxy_cache.py  
**Notes:** Module-level async state pattern from Phase 24 is the anchor.

---

## Update Timing

### Q1: When the admin saves a new concurrency value, when should it take effect?

| Option | Description | Selected |
|--------|-------------|----------|
| TTL-based refresh — same pattern as proxy_cache.py | Semaphore capacity cached alongside proxy config. On TTL expiry (60s), next download checks DB: if value changed, old semaphore drains, new one created. Change takes effect within 60s. | ✓ |
| Immediate invalidation | When admin saves, PATCH API resets semaphore TTL to 0. Next download call recreates immediately. Requires API endpoint to know about semaphore module. | |

**User's choice:** TTL-based refresh  
**Notes:** 60s window is well within "next download job" since jobs run every 15 min.

### Q2: What happens to downloads that are already in-flight when the semaphore is replaced?

| Option | Description | Selected |
|--------|-------------|----------|
| Let them finish on the old semaphore | In-flight downloads complete normally. New downloads acquire from new semaphore. Brief transition period acceptable given 60s TTL. | ✓ |
| Cancel and retry | Force-cancel downloads holding old semaphore slots, then requeue. Much more complex. | |

**User's choice:** Let them finish on the old semaphore  
**Notes:** No cancellation logic needed. Clean natural drain.

---

## Admin UI Placement

### Q1: Where should the concurrency setting appear on /configuration/admin?

| Option | Description | Selected |
|--------|-------------|----------|
| New 'Download Performance' section (above proxy section) | Clean dedicated section. Future download settings could go here too. | |
| New section just below proxy section | Same but placed after proxy block. | |
| Inside the proxy section | Misleading — concurrency applies to all downloads, not just proxied ones. | |
| Other (free text) | "merge all download related setting in one section (i.e. parallel downloads, proxies and cookies) one section but visually separated" | ✓ |

**User's choice:** One combined "Download Settings" section with visual separators for Parallel Downloads, Residential Proxy, and Cookies subsections  
**Notes:** All three download-related admin controls merged. Parallel Downloads positioned first.

### Q2: Should the existing Proxy and Cookies sections be visually merged into this new combined section in Phase 25?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — combine everything in Phase 25 | Phase 25 restructures the admin page: one section with subsections. Clean final result. | ✓ |
| No — just add the new concurrency subsection | Add concurrency as new top-level section; leave existing sections untouched. | |

**User's choice:** Yes — combine everything in Phase 25  
**Notes:** Existing proxy and cookie sections are restructured into subsections of "Download Settings."

---

## Number Input UX

### Q1: How should the admin set the concurrency value?

| Option | Description | Selected |
|--------|-------------|----------|
| Slider (1–10) + Save button | mat-slider gives visual feedback on the 1–10 range. Save/Discard buttons confirm change — consistent with proxy save pattern. | ✓ |
| Number input + stepper arrows + Save button | mat-form-field type=number. Matches proxy URL card Save/Discard style exactly. Less visual. | |
| Inline segmented buttons (1 / 2 / 3 / 5 / 10) | mat-button-toggle-group with preset values. Autosaves. Limited to preset values. | |

**User's choice:** Slider (1–10) + Save button  
**Notes:** Visual range representation preferred over bare number input.

### Q2: Should the slider show tick marks at each integer (1–10) or be smooth?

| Option | Description | Selected |
|--------|-------------|----------|
| Tick marks at each integer | mat-slider discrete mode: step=1, showTickMarks=true. Snaps to integers, makes valid values obvious. | ✓ |
| Smooth, no ticks | Continuous slider. Value rounds to nearest integer. Slightly less precise. | |

**User's choice:** Tick marks at each integer  
**Notes:** Discrete mode, step=1.

---

## Claude's Discretion

- File naming for extended proxy_cache.py (rename to download_cache.py or keep as proxy_cache.py) — planner decides
- Visual separator element within "Download Settings" section (`<hr>` vs `<mat-divider>`) — planner decides
- Exact API endpoint path for concurrency config (dedicated `/download-concurrency` vs general `/system-config`) — planner decides
- Whether to add a `mat-form-field` label + value display alongside the slider, or rely on slider thumb label alone — planner decides

## Deferred Ideas

None — discussion stayed within phase scope.
