# Requirements: BrainSuite Platform Connector v1.4

**Defined:** 2026-05-14
**Core Value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## v1 Requirements

### Proxy Downloads

- [ ] **PROXY-01**: DV360 video creatives download successfully on GCP Cloud Run via residential proxy (public ad creatives succeed without cookies when proxy is enabled)
- [ ] **PROXY-02**: Google Ads video creatives download successfully on GCP Cloud Run via residential proxy (same yt-dlp path as DV360)
- [ ] **PROXY-03**: bgutil PO token plugin (`bgutil-ytdlp-pot-provider`) is installed in the backend Docker image and invoked automatically by yt-dlp for format URL requests — no manual token management required
- [ ] **PROXY-04**: Download retry order is cookieless-first — residential IP (no cookies) → primary cookies → backup cookies → fail; existing cookie slots are preserved unchanged
- [x] **PROXY-05**: A SuperAdmin can configure the residential proxy URL (stored Fernet-encrypted in `SystemConfig`) and toggle the proxy on/off from the `/configuration/admin` UI
- [ ] **PROXY-06**: Proxy credentials (URL including embedded username/password) are never written to application logs or included in error messages or job output

### Dashboard Filters

- [x] **DASH-01**: A user can filter the creative grid by metadata field value using a searchable autocomplete input; suggestions are limited to values belonging to the user's organization (no cross-org leakage)
- [x] **DASH-02**: A user can filter the creative grid by one or more ad accounts using a multi-select filter; selecting multiple accounts shows creatives from all selected accounts
- [ ] **DASH-03**: A user can filter the creative grid by video duration range using a dual-handle slider; legacy assets with no duration data are excluded from the filtered view and a count callout is shown

## v2 Requirements

### Real-time Infrastructure

- **SSE-03**: SSE transport upgrades to Redis pub/sub at 50+ concurrent SuperAdmin users — DB polling no longer sufficient

### Account Configuration

- **META-01**: A user can set default metadata field values at the ad account connection level (connection_metadata_defaults table)
- **META-02**: Default metadata values from connection config are used as fallback when no asset-level value exists at sync time

### Tech Debt

- **DEBT-01**: Alembic migration tree merged to a single head — `alembic upgrade head` (singular) works reliably on fresh installs

## Out of Scope

| Feature | Reason |
|---------|--------|
| Filter state URL persistence | v1.5 candidate — requires query param serialization contract and back-button state management; scope too broad for v1.4 |
| Saved filter presets | Needs new DB table + state machine; deferred |
| Per-tenant proxy cost tracking | API integration with provider billing; operational concern, not core feature |
| Proxy per-provider selection UI | Single encrypted URL is sufficient; provider is an ops decision |
| TikTok proxy support | TikTok downloads use yt-dlp impersonation, not residential proxy; separate problem |
| Per-tenant AI inference spend cap (AI-01) | Platform-wide GEMINI_API_KEY; per-tenant cap not feasible without per-org key management |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROXY-01 | Phase 20 | Pending |
| PROXY-02 | Phase 20 | Pending |
| PROXY-03 | Phase 20 | Pending |
| PROXY-04 | Phase 20 | Pending |
| PROXY-06 | Phase 20 | Pending |
| PROXY-05 | Phase 21 | Complete |
| DASH-01 | Phase 22 | Complete |
| DASH-02 | Phase 22 | Complete |
| DASH-03 | Phase 23 | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-14*
*Last updated: 2026-05-14 — traceability filled after roadmap creation*
