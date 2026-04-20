---
phase: 13
slug: field-mapping-editor-mandatory-field-enforcement
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-20
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + Jasmine/Karma (frontend) |
| **Config file** | `backend/tests/conftest.py`, `karma.conf.js` |
| **Quick run command** | `pytest tests/test_phase13_field_mappings.py -x` |
| **Full suite command** | `pytest tests/ -k "phase13 or brainsuite" --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_phase13_field_mappings.py -x`
- **After every plan wave:** Run `pytest tests/ -k "phase13 or brainsuite" --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green (`pytest tests/ -k "phase13 or brainsuite" --tb=short` + `ng test --watch=false --code-coverage`)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-xx-01 | 01 | 1 | FMAP-01 | T-13-01 | `organization_id` check before field mapping queries | unit | `pytest tests/test_phase13_field_mappings.py::test_get_field_mappings_video -x` | ❌ W0 | ⬜ pending |
| 13-xx-02 | 01 | 1 | FMAP-02 | T-13-01 | `organization_id` check before field mapping queries | unit | `pytest tests/test_phase13_field_mappings.py::test_get_field_mappings_static -x` | ❌ W0 | ⬜ pending |
| 13-xx-03 | 02 | 1 | FMAP-03 | T-13-02 | Alphanumeric-only field name validation via Pydantic | unit | `pytest tests/test_phase13_field_mappings.py::test_add_custom_field_video -x` | ❌ W0 | ⬜ pending |
| 13-xx-04 | 02 | 1 | FMAP-04 | T-13-02 | Alphanumeric-only field name validation via Pydantic | unit | `pytest tests/test_phase13_field_mappings.py::test_add_custom_field_static -x` | ❌ W0 | ⬜ pending |
| 13-xx-05 | 02 | 1 | FMAP-05 | T-13-02 | Standard fields cannot be deleted; org isolation enforced | unit | `pytest tests/test_phase13_field_mappings.py::test_remove_custom_field -x` | ❌ W0 | ⬜ pending |
| 13-xx-06 | 02 | 2 | FMAP-06 | T-13-03 | Mandatory toggle persists in DB; pipeline reads from DB, not UI state | unit | `pytest tests/test_phase13_field_mappings.py::test_toggle_mandatory -x` | ❌ W0 | ⬜ pending |
| 13-xx-07 | 03 | 2 | FMAP-07 | T-13-04 | Asset stays UNSCORED + notification created for missing mandatory field | integration | `pytest tests/test_phase13_field_mappings.py::test_scoring_skips_missing_mandatory -x` | ❌ W0 | ⬜ pending |
| 13-xx-08 | 03 | 2 | PIPE-02 | T-13-04 | Assets not queued for org with missing credentials/app_name | integration | `pytest tests/test_phase13_field_mappings.py::test_pipeline_guard_missing_config -x` | ❌ W0 | ⬜ pending |
| 13-xx-09 | 03 | 2 | PIPE-03 | — | Sticky warning banner appears when config incomplete | e2e | `ng test --include="**/*brainsuite-apps*.spec.ts" -k "incomplete-warning"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_phase13_field_mappings.py` — stubs for FMAP-01 through PIPE-02
- [ ] `backend/tests/test_phase13_scoring_pipeline.py` — covers FMAP-07 and PIPE-02 scoring guards
- [ ] `frontend/src/app/features/configuration/pages/brainsuite-apps.component.spec.ts` (extend Phase 12 tests) — covers FMAP-05/06 UI interactions + PIPE-03 banner
- [ ] Integration test fixtures: create test org with metadata fields, BrainsuiteApps (VIDEO + STATIC), CreativeAssets with metadata values
- [ ] Integration tests for auto-match logic (server-side)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slide panel opens/closes with CSS animation | FMAP-01/02 | Visual animation cannot be unit tested | Open field mapping panel, verify `transform: translateX()` animation runs smoothly |
| Mandatory field visual indicator (badge/asterisk) | FMAP-06 | DOM presence verifiable via spec but visual styling requires manual check | Toggle mandatory on a field, verify visual distinction in UI (badge, asterisk, or color change as per UI-SPEC) |
| YouTube cookies DB-backed update without container restart | Additional scope | Requires Docker environment with live container | POST to cookies endpoint, verify change takes effect without `docker-compose restart` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
