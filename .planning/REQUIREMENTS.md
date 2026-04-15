# Requirements: BrainSuite Platform Connector

**Defined:** 2026-04-15
**Core Value:** A user can connect all their ad accounts, see every creative's performance metrics alongside its BrainSuite effectiveness score, and immediately know which creatives to scale or kill.

## v1.2 Requirements

### BrainSuite Org Config (BSCFG)

- [ ] **BSCFG-01**: Admin can save BrainSuite Client ID and Client Secret per organization via the Settings page
- [ ] **BSCFG-02**: Admin can configure the video app name per organization (replaces hardcoded `ACE_VIDEO_SMV_API` in the scoring endpoint URL)
- [ ] **BSCFG-03**: Admin can configure the static app name per organization (replaces hardcoded `ACE_STATIC_SOCIAL_STATIC_API` in the scoring endpoint URL)
- [ ] **BSCFG-04**: BrainSuite configuration is accessible as a dedicated section within the existing Settings page

### API Field Mapping (FMAP)

- [ ] **FMAP-01**: Admin can view and update the metadata field mapped to each of the 12 standard video API fields: channel, projectName, assetName, assetStage, assetLanguage, brandNames, voiceOver, voiceOverLanguage, intendedMessages, intendedMessagesLanguage, brandValues, brandValuesLanguage
- [ ] **FMAP-02**: Admin can view and update the metadata field mapped to each of the 8 standard static API fields: channel, projectName, assetLanguage, iconicColorScheme, intendedMessages, intendedMessagesLanguage, brandValues, brandValuesLanguage
- [ ] **FMAP-03**: Admin can add a custom API field for the video app and select any organization metadata field to map it to
- [ ] **FMAP-04**: Admin can add a custom API field for the static app and select any organization metadata field to map it to
- [ ] **FMAP-05**: Admin can remove a custom field mapping (standard fields cannot be removed, only left unmapped)
- [ ] **FMAP-06**: Admin can mark any field (standard or custom) as mandatory
- [ ] **FMAP-07**: For an asset where a mandatory field has no metadata mapping or no value, scoring is skipped and the user is notified which field(s) are missing
- [ ] **FMAP-08**: `brainsuite_brand_values` (TEXT) and `brainsuite_brand_values_language` (SELECT, language enum) are seeded as default non-mandatory metadata fields for all organizations via Alembic migration and new-org provisioning

### Scoring Pipeline Integration (PIPE)

- [ ] **PIPE-01**: Scoring pipeline reads Client ID, Client Secret, app names, and field mappings from the organization's DB config instead of global `.env` settings
- [ ] **PIPE-02**: Assets for an organization with incomplete BrainSuite config (missing credentials or app name) remain UNSCORED and are not queued for scoring
- [ ] **PIPE-03**: Org admin sees a visible warning in the UI when their BrainSuite configuration is incomplete or missing

### Validation & Safety (VSAF)

- [ ] **VSAF-01**: Admin can click "Test Connection" to fire a live BrainSuite authentication request and see inline success or failure feedback
- [ ] **VSAF-02**: When an admin saves changes to a BrainSuite config and the organization has already-scored assets, a prompt appears asking: keep existing scores or re-score all previously scored assets under the new configuration

## Future Requirements

### External Notifications

- **NOTIF-01**: User receives Slack notification when token expires or sync fails
- **NOTIF-02**: User receives email notification when score threshold is crossed
- **NOTIF-03**: User can configure notification preferences per channel

### AI Inference Controls

- **AI-01**: Per-tenant daily AI inference spend cap configurable by org admin

## Out of Scope

| Feature | Reason |
|---------|--------|
| Moving GEMINI_API_KEY to DB | Only BrainSuite credentials are per-org; Gemini key is platform-wide |
| Real-time notifications (SSE/WebSocket) | Polling sufficient for v1.x event frequency |
| Mobile app | Web-first |
| Ad copy / text creative scoring | Not supported by BrainSuite API |
| Creative identity across platforms | Deferred to v2 |
| Performer badge threshold fix (3→10) | Intentional decision — 3 is correct for this deployment |

## Traceability

*(Populated by roadmapper — roadmap not yet created)*

| Requirement | Phase | Status |
|-------------|-------|--------|
| BSCFG-01 | TBD | Pending |
| BSCFG-02 | TBD | Pending |
| BSCFG-03 | TBD | Pending |
| BSCFG-04 | TBD | Pending |
| FMAP-01 | TBD | Pending |
| FMAP-02 | TBD | Pending |
| FMAP-03 | TBD | Pending |
| FMAP-04 | TBD | Pending |
| FMAP-05 | TBD | Pending |
| FMAP-06 | TBD | Pending |
| FMAP-07 | TBD | Pending |
| FMAP-08 | TBD | Pending |
| PIPE-01 | TBD | Pending |
| PIPE-02 | TBD | Pending |
| PIPE-03 | TBD | Pending |
| VSAF-01 | TBD | Pending |
| VSAF-02 | TBD | Pending |

**Coverage:**
- v1.2 requirements: 17 total
- Mapped to phases: 0
- Unmapped: 17 ⚠️ (roadmap not yet created)

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-15 after initial definition*
