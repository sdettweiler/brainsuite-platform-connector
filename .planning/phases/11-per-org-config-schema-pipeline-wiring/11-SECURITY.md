---
phase: 11
slug: per-org-config-schema-pipeline-wiring
status: verified
threats_open: 0
asvs_level: 2
created: 2026-04-16
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Service layer → DB | OrgBrainsuiteConfig stores encrypted secrets; column type must not leak plain text | Fernet-encrypted client_secret (String(1000)) |
| Alembic migration → DB | DDL must enforce FK integrity and unique constraints | Schema structure only |
| Migration → DB | Seed data must be idempotent and not corrupt existing metadata | Metadata field definitions |
| Auth endpoint → DB | ORM inserts during registration must not fail the registration flow | New org metadata provisioning |
| scoring_job.py → OrgBrainsuiteConfig | Reads encrypted secret from DB — must decrypt only in-memory, never log or return | Decrypted BrainSuite client_secret |
| BrainSuiteScoreService → BrainSuite API | Per-org credentials used for auth; token cached per org to prevent cross-tenant leakage | OAuth tokens keyed by org_id |
| _mark_unscored state transition | Must only transition PENDING assets, never PROCESSING (live job IDs) | Asset scoring_status field |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-11-01 | Information Disclosure | OrgBrainsuiteConfig.client_secret_encrypted | mitigate | Column is String(1000) not Text; no plain client_secret column exists; value Fernet-encrypted at service layer | closed |
| T-11-02 | Tampering | org_brainsuite_config FK | mitigate | ON DELETE CASCADE on organization_id FK; UniqueConstraint("organization_id") prevents duplicate configs per org | closed |
| T-11-03 | Tampering | Seed migration re-run | mitigate | ON CONFLICT (organization_id, name) DO NOTHING on metadata_fields inserts; idempotent on re-run | closed |
| T-11-04 | Denial of Service | auth.py flush during registration | accept | Two extra flush() calls within existing transaction budget — negligible latency | closed |
| T-11-05 | Information Disclosure | scoring_job.py decrypt_token | mitigate | client_secret decrypted in-memory only; logger emits field name string only, never the decrypted value | closed |
| T-11-06 | Spoofing | Per-org token cache | mitigate | Token dict keyed by org_id in both score services; cross-org token access structurally impossible | closed |
| T-11-07 | Elevation of Privilege | _mark_unscored state guard | mitigate | Guards on scoring_status == "PENDING" before writing UNSCORED; PROCESSING assets never touched | closed |
| T-11-08 | Information Disclosure | Score services logging | accept | Only client_id[:8] prefix emitted in logs; no credential values in log output | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-11-01 | T-11-04 | Two extra db.flush() calls in auth.py new-org registration are within the existing transaction budget; latency impact is negligible | Plan (documented in 11-02-PLAN.md threat model) | 2026-04-16 |
| AR-11-02 | T-11-08 | Score services log URL and status code but not auth headers or credentials; only client_id[:8] prefix appears in log output; no remediation required | Plan (documented in 11-03-PLAN.md threat model) | 2026-04-16 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-16 | 8 | 8 | 0 | gsd-security-auditor (ASVS L2) |

### Audit Detail — 2026-04-16

| Threat ID | Evidence |
|-----------|----------|
| T-11-01 | `backend/app/models/brainsuite_config.py:28` — `String(1000)` confirmed; no plain `client_secret` column |
| T-11-02 | `backend/app/models/brainsuite_config.py:25,41` — `ondelete="CASCADE"` FK + `UniqueConstraint("organization_id")`; mirrored in Alembic DDL `s0t1u2v3w4x5:24,33` |
| T-11-03 | `backend/alembic/versions/t1u2v3w4x5y6_seed_brand_values_metadata_fields.py:80` — `ON CONFLICT (organization_id, name) DO NOTHING` |
| T-11-05 | `backend/app/services/sync/scoring_job.py:207,217` — logger emits string literal `"client_secret"` only; decrypted value is local variable, never passed to logger |
| T-11-06 | `backend/app/services/brainsuite_score.py:41-42`, `brainsuite_static_score.py:51-52` — `_tokens: dict[str, str]` keyed by `org_id` in both services |
| T-11-07 | `backend/app/services/sync/scoring_job.py:426` — `score_row.scoring_status == "PENDING"` guard confirmed |
| T-11-04 | Accepted risk AR-11-01 |
| T-11-08 | Accepted risk AR-11-02 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-16
