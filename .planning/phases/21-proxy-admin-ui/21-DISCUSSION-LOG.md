# Phase 21: Proxy Admin UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 21-proxy-admin-ui
**Areas discussed:** Toggle + URL save behavior, URL display when configured, Test connection button, Card position in admin page

---

## Toggle + URL Save Behavior

### Q1: How should the enable/disable toggle and proxy URL be saved?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate saves | Toggle is instant (one PUT call on change, like scoring toggle). URL has its own edit mode — click Replace, paste URL, click Save. Two independent actions, no coupling. | ✓ |
| Single form | Both toggle and URL are in one form. Changes aren't applied until the user clicks a 'Save' button. Consistent but adds friction for quick enable/disable. | |

**User's choice:** Separate saves

### Q2: When the toggle is OFF, should the URL input be visually disabled/greyed out?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, grey it out | URL input shown but disabled when proxy is off — clear that the URL only matters when enabled. | ✓ |
| No, always editable | URL input is always active regardless of toggle state — simpler, lets admin pre-configure URL before enabling. | |

**User's choice:** Yes, grey it out

---

## URL Display When Configured

### Q1: When a proxy URL is saved, how should it appear in the card?

| Option | Description | Selected |
|--------|-------------|----------|
| Host-visible redaction | Show `http://••••••@geo.iproyal.com:12321` — credentials hidden, host/port visible for debugging which provider is active. Mirrors Phase 20 D-05 redaction format. | ✓ |
| Full bullet mask | Show `••••••••••••••••••••` only (identical to cookie slots). Simple, no structural parsing needed. | |
| 'Configured' indicator only | Just a green checkmark + 'URL configured' label. Minimal info. | |

**User's choice:** Host-visible redaction

### Q2: Who extracts the host for the masked display — backend or frontend?

| Option | Description | Selected |
|--------|-------------|----------|
| Backend returns masked string | GET /super-admin/proxy-config returns a pre-masked string. No URL parsing in the frontend. Keeps credential logic server-side only. | ✓ |
| Frontend parses and masks | Backend returns is_configured: true and maybe the host portion. Frontend does the display formatting. | |

**User's choice:** Backend returns masked string

---

## Test Connection Button

### Q1: Should the card include a 'Test Proxy' button to verify the URL works?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip it | Phase 20 (D-09) decided validation is a manual ops step — trigger a real sync and check logs. | |
| Include it | Add a 'Test Connection' button that hits a light backend check — HTTP reachability, pass/fail. | ✓ |

**User's choice:** Include it

### Q2: What should the proxy test actually do on the backend?

| Option | Description | Selected |
|--------|-------------|----------|
| HTTP reachability check | Make an HTTPS request through the proxy to a known stable URL (e.g., https://www.youtube.com/) with a short timeout. Pass = response received; Fail = timeout or connection error. | ✓ |
| yt-dlp format extraction | Run a real yt-dlp info-extraction (no download) on a known video ID through the proxy. Stronger proof but slower (3-10s). | |

**User's choice:** HTTP reachability check

---

## Card Position in Admin Page

### Q1: Where in the /configuration/admin page should the Residential Proxy card appear?

| Option | Description | Selected |
|--------|-------------|----------|
| Section 1 — before YouTube Cookies | Proxy + cookies are both download-layer config. Groups related config at top. | ✓ |
| Section 2 — after YouTube Cookies | YouTube Cookies stays first (already there), Residential Proxy follows immediately. | |
| Last section | Append at the bottom after Scoring Controls. Less disruption to existing order. | |

**User's choice:** Section 1 — before YouTube Cookies

---

## Claude's Discretion

None — all gray areas were decided by the user.

## Deferred Ideas

None — discussion stayed within phase scope.
