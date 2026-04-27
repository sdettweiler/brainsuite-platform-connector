# Roadmap: BrainSuite Platform Connector

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-25) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Insights + Intelligence** — Phases 5–10 (shipped 2026-04-15) — [archive](milestones/v1.1-ROADMAP.md)
- 🔄 **v1.2 BrainSuite Configuration** — Phases 11–13 (in progress — started 2026-04-15)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-25</summary>

- [x] Phase 1: Infrastructure Portability (3/3 plans) — completed 2026-03-20
- [x] Phase 2: Security Hardening (6/6 plans) — completed 2026-03-23
- [x] Phase 3: BrainSuite Scoring Pipeline (6/6 plans) — completed 2026-03-24
- [x] Phase 4: Dashboard Polish + Reliability (4/4 plans) — completed 2026-03-25

</details>

<details>
<summary>✅ v1.1 Insights + Intelligence (Phases 5–10) — SHIPPED 2026-04-15</summary>

- [x] Phase 5: BrainSuite Image Scoring (4/4 plans) — completed 2026-03-27
- [x] Phase 6: Historical Backfill + Score History Schema (1/1 plans) — completed 2026-03-30
- [x] Phase 7: Score Trend, Performer Highlights + Performance Tab (3/3 plans) — completed 2026-03-30
- [x] Phase 8: Score-to-ROAS Correlation (2/2 plans) — completed 2026-03-31
- [x] Phase 9: AI Metadata Auto-Fill (3/3 plans) — completed 2026-04-15
- [x] Phase 10: In-App Notifications (2/2 plans) — completed 2026-04-15

</details>

### v1.2 BrainSuite Configuration (Phases 11–13)

- [x] **Phase 11: Per-Org Config Schema + Pipeline Wiring** — DB tables, metadata seed, pipeline reads from DB (completed 2026-04-16)
- [x] **Phase 12: Credentials + App Name Settings UI** — Settings section, Test Connection, re-score prompt (completed 2026-04-17)
- [x] **Phase 13: Field Mapping Editor + Mandatory Field Enforcement** — mapping UI, custom fields, mandatory logic, pipeline guards (completed 2026-04-21)

## Phase Details

### Phase 11: Per-Org Config Schema + Pipeline Wiring
**Goal**: The database can store per-org BrainSuite configuration and the scoring pipeline reads from it instead of global env vars
**Depends on**: Phase 10 (v1.1 complete)
**Requirements**: FMAP-08, PIPE-01
**Success Criteria** (what must be TRUE):
  1. `org_brainsuite_config` table exists with columns for client_id, client_secret (encrypted), video_app_name, static_app_name, org_id FK
  2. `org_brainsuite_field_mappings` table exists with columns for org_id, app_type, api_field_name, metadata_field_id, is_mandatory, is_custom
  3. `brainsuite_brand_values` (TEXT) and `brainsuite_brand_values_language` (SELECT) metadata fields are seeded for all existing orgs via Alembic migration and injected during new-org provisioning
  4. Scoring pipeline (`brainsuite_score.py`, `brainsuite_static_score.py`) loads client credentials and app names from the org's DB row, not from `.env`
  5. Pipeline falls through gracefully (no exception, asset stays UNSCORED) when an org has no config row yet
**Plans:** 3/3 plans complete

Plans:
- [x] 11-01-PLAN.md — SQLAlchemy models + schema migration for org_brainsuite_config and org_brainsuite_field_mappings
- [x] 11-02-PLAN.md — Seed brand_values metadata fields via Alembic + new-org provisioning in auth.py
- [x] 11-03-PLAN.md — Re-wire scoring pipeline to read per-org credentials from DB

### Phase 12: Credentials + App Name Settings UI
**Goal**: Org admins can configure and validate their BrainSuite credentials and app names through the Settings page
**Depends on**: Phase 11
**Requirements**: BSCFG-01, BSCFG-02, BSCFG-03, BSCFG-04, VSAF-01, VSAF-02
**Success Criteria** (what must be TRUE):
  1. Settings page contains a dedicated "BrainSuite Configuration" section (BSCFG-04) with fields for Client ID, Client Secret, Video App Name, and Static App Name
  2. Admin can save credentials and app names; values persist to DB and are loaded on next page visit
  3. "Test Connection" button fires a live BrainSuite authentication request and displays inline success or failure feedback without leaving the page
  4. When saving changes to an org that already has scored assets, a confirmation dialog appears offering "Keep existing scores" or "Re-score all assets under new config"
  5. Client Secret field is masked (password input) and the stored value is never returned in plain text to the frontend
**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md -- Migration + model updates + pipeline re-wire (system_app_name)
- [x] 12-02-PLAN.md -- Backend API endpoints (credentials CRUD, test-connection, rescore)
- [x] 12-03-PLAN.md -- Frontend credentials section, accordion, re-score dialog

### Phase 13: Field Mapping Editor + Mandatory Field Enforcement
**Goal**: Org admins can configure exactly which metadata fields map to each BrainSuite API field, mark fields mandatory, and assets with missing mandatory data are blocked from scoring with an actionable admin warning
**Depends on**: Phase 12
**Requirements**: FMAP-01, FMAP-02, FMAP-03, FMAP-04, FMAP-05, FMAP-06, FMAP-07, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Admin can view all 12 standard video API fields and all 8 standard static API fields, each showing its currently mapped metadata field (or "unmapped")
  2. Admin can change the metadata field mapped to any standard field and save; admin can add a named custom API field for video or static and map it to any org metadata field; admin can remove a custom field mapping
  3. Admin can toggle the mandatory flag on any field (standard or custom); mandatory fields are visually distinguished in the mapping editor
  4. When the scoring pipeline encounters an asset where a mandatory field has no mapped metadata field or the asset has no value for that field, the asset is skipped (stays UNSCORED) and a notification is created listing the missing field(s)
  5. Org admin sees a persistent warning banner or alert in the Settings page when their BrainSuite config is incomplete (missing credentials, app name, or any mandatory field with no metadata mapping)
**Additional scope (surfaced during Phase 12 UAT 2026-04-17)**:
  - YouTube cookies DB-backed storage: store cookies in `org_brainsuite_config` (or dedicated table), add admin API endpoint to update without container restart, update `dv360_sync.py` to read from DB. Currently cookies are baked into env var requiring a Docker restart to rotate.
**Plans**: 4 plans

Plans:
- [x] 13-01-PLAN.md -- Data layer: model update (brainsuite_app_id FK), Alembic migration, Pydantic schemas
- [x] 13-02-PLAN.md -- Backend API: GET/PUT field-mapping endpoints + Wave 0 test stubs
- [x] 13-03-PLAN.md -- Pipeline enforcement: FMAP-07 mandatory field guard + notification
- [x] 13-04-PLAN.md -- Frontend: field mapping slide panel, trigger button, warning banner

**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Portability | v1.0 | 3/3 | Complete | 2026-03-20 |
| 2. Security Hardening | v1.0 | 6/6 | Complete | 2026-03-23 |
| 3. BrainSuite Scoring Pipeline | v1.0 | 6/6 | Complete | 2026-03-24 |
| 4. Dashboard Polish + Reliability | v1.0 | 4/4 | Complete | 2026-03-25 |
| 5. BrainSuite Image Scoring | v1.1 | 4/4 | Complete | 2026-03-27 |
| 6. Historical Backfill + Score History Schema | v1.1 | 1/1 | Complete | 2026-03-30 |
| 7. Score Trend, Performer Highlights + Performance Tab | v1.1 | 3/3 | Complete | 2026-03-30 |
| 8. Score-to-ROAS Correlation | v1.1 | 2/2 | Complete | 2026-03-31 |
| 9. AI Metadata Auto-Fill | v1.1 | 3/3 | Complete | 2026-04-15 |
| 10. In-App Notifications | v1.1 | 2/2 | Complete | 2026-04-15 |
| 11. Per-Org Config Schema + Pipeline Wiring | v1.2 | 3/3 | Complete   | 2026-04-16 |
| 12. Credentials + App Name Settings UI | v1.2 | 3/3 | Complete   | 2026-04-17 |
| 13. Field Mapping Editor + Mandatory Field Enforcement | v1.2 | 4/4 | Complete    | 2026-04-21 |
| 14. YouTube Cookies Admin UI | v1.2 | 3/3 | Complete   | 2026-04-27 |

### Phase 14: YouTube Cookies Admin UI

**Goal:** Org admins can store and rotate YouTube/DV360 cookies through the Settings UI without requiring a Docker restart or direct env var access. Cookies are persisted in the database per-org, the admin API endpoint accepts updates, and dv360_sync.py reads cookies from DB instead of env vars.
**Requirements**: COOK-01, COOK-02, COOK-03
**Depends on:** Phase 13
**Plans:** 3/3 plans complete

Plans:
- [x] TBD (run /gsd-plan-phase 14 to break down) (completed 2026-04-27)
