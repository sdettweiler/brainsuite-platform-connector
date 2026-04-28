# Phase 14: YouTube Cookies Admin UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 14-youtube-cookies-admin-ui
**Areas discussed:** Cookie storage, Primary + backup slots, Settings UI placement (revised to Admin section), Cookie input UX

---

## Gray Area Selection

| Option | Selected |
|--------|----------|
| Cookie storage | ✓ |
| Primary + backup slots | ✓ |
| Settings UI placement | ✓ |
| Cookie input UX | ✓ |

---

## Cookie Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Add to org_brainsuite_config | Add columns to existing table | |
| New system_config singleton table | New table with one guaranteed row | ✓ |

**User's choice:** System-global via new `system_config` singleton table

**Notes:** User clarified mid-discussion that this is a SuperAdmin-only feature, not a per-org setting. This changed the storage decision from per-org (`org_brainsuite_config`) to system-global (`system_config` singleton). The singleton is enforced via a `singleton_guard` VARCHAR(1) UNIQUE DEFAULT 'X' column.

---

## Primary + Backup Slots

| Option | Description | Selected |
|--------|-------------|----------|
| Two slots (primary + backup) | Mirrors existing env var design, zero-downtime rotation | ✓ |
| One slot only | Simpler, no fallback | |

**User's choice:** Two slots (primary + backup)

**Notes:** User also added significant detail: fire a bell notification (COOKIE_FAILED) when a cookie fails, clicking the notification routes to the Admin cookies page, and the page shows clear cookie health indicators per slot.

**Follow-up — Notification timing:**

| Option | Description | Selected |
|--------|-------------|----------|
| On download failure (reactive) | Fire when yt-dlp exhausts all slots | ✓ |
| Proactive scheduled check | Fires COOKIE_EXPIRING_SOON 24h before expiry | |

---

## Settings UI Placement

**User clarification:** This is a SuperAdmin-only feature with a new "Admin" top-level menu under Configuration. The cookies UI lives there, not in the per-org BrainSuite Settings page.

**New Admin menu scope selected by user:**
- YouTube Cookies ✓
- SuperAdmin Management ✓
- System-wide Org List ✓

---

## Cookie Input UX

| Option | Description | Selected |
|--------|-------------|----------|
| Textarea + masked after save | Paste Netscape format, masked with Reveal toggle | ✓ |
| Textarea always visible | Plain text, easier to debug | |

**User's choice:** Textarea + masked after save (same UX as Client Secret)

**Follow-up — Validation on save:**

| Option | Description | Selected |
|--------|-------------|----------|
| Expiry-based status (VALID/EXPIRED/MISSING) | Backend checks timestamps | ✓ |
| Health shown on failure only | No status badges | |

---

## System Config Storage (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| New system_config singleton table | Typed columns, enforced one row | ✓ |
| Key-value system_settings table | Generic, flexible | |

---

## Org List Scope (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only: name, slug, user count, created | Simple visibility | ✓ |
| Full management: create/delete orgs | Heavy scope, deferred | |

---

## Claude's Discretion

- `Text` vs `VARCHAR` for cookie columns — Text chosen (cookies are multi-KB)
- Single `AdminComponent` vs separate page components — single component preferred unless org list needs lazy loading
- COOKIE_FAILED deeplink routing — wire to existing notification bell `data.deeplink` handler if already supported by Phase 10 implementation

## Deferred Ideas

- Org create/delete (future Admin phase)
- Proactive COOKIE_EXPIRING_SOON notification (future enhancement)
- Per-org cookie overrides (future multi-DV360-account scenario)
- Cookie file upload (.txt) — textarea covers the use case
