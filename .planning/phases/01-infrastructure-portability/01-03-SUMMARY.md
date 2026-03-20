---
phase: 01-infrastructure-portability
plan: 03
subsystem: infra
tags: [makefile, setup-script, dotenv, fernet, cryptography, developer-experience]

# Dependency graph
requires:
  - phase: 01-01
    provides: docker-compose.yml, docker-compose.dev.yml, .env.example with all required env var names
  - phase: 01-02
    provides: object storage layer and confirmed env var list (S3_ENDPOINT_URL, S3_BUCKET_NAME, etc.)
provides:
  - scripts/setup.py — interactive .env generator with auto-generated SECRET_KEY and TOKEN_ENCRYPTION_KEY
  - Makefile — dev/up/down/logs/setup targets with automatic .env detection
affects: [all-phases, onboarding, deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Interactive setup script pattern: stdin.isatty() guard for non-interactive --dry-run mode"
    - "Makefile .env guard: [ ! -f .env ] check in dev target before docker compose"
    - "Secret generation: secrets.token_hex(32) for SECRET_KEY, Fernet.generate_key() for TOKEN_ENCRYPTION_KEY"

key-files:
  created:
    - scripts/setup.py
    - Makefile
  modified: []

key-decisions:
  - "setup.py uses sys.stdin.isatty() check so --dry-run < /dev/null works without prompts — uses defaults when not a TTY"
  - "Redirect URIs auto-derived from BASE_URL to avoid drift between base URL and callback URIs"
  - "Platform credentials are optional (blank to skip) — only DB, storage, and auto-generated keys required for local dev"
  - "Makefile dev target includes --build flag so image rebuilds happen automatically on Dockerfile changes"

patterns-established:
  - "Developer onboarding: clone -> make dev -> prompted for secrets -> stack starts automatically"
  - "Non-interactive CI validation: python3 scripts/setup.py --dry-run < /dev/null"

requirements-completed: [INFRA-08]

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 01 Plan 03: Setup Script and Makefile Summary

**Interactive `scripts/setup.py` generates a valid .env from prompts (auto-generates SECRET_KEY via `secrets.token_hex` and TOKEN_ENCRYPTION_KEY via `Fernet.generate_key`), and `Makefile` provides `make dev` as the single onboarding command that auto-runs setup when .env is missing.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T15:38:47Z
- **Completed:** 2026-03-20T15:40:53Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `scripts/setup.py` prompts for all secret groups (DB, S3/MinIO, Meta, TikTok, Google, DV360, BrainSuite API key, exchange rate) and writes a valid .env
- `SECRET_KEY` (64 hex chars) and `TOKEN_ENCRYPTION_KEY` (Fernet key) are auto-generated and displayed to the user
- `Makefile` with `dev`, `up`, `down`, `logs`, `setup` targets — `make dev` is now the single command to onboard a new developer
- `--dry-run` flag uses defaults when stdin is not a TTY, enabling CI validation with `< /dev/null`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create interactive setup script** - `ec3d0d1` (feat)
2. **Task 2: Create Makefile with dev/up/down/logs targets** - `7106e8d` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `scripts/setup.py` — interactive .env generator with Fernet key and hex secret generation, --dry-run support, getpass for secrets
- `Makefile` — dev/up/down/logs/setup targets; dev auto-runs setup.py when .env missing, uses both compose files with --build

## Decisions Made

- `sys.stdin.isatty()` guard added to `prompt()` so non-interactive runs (piped from /dev/null) use defaults without blocking on input — this is essential for the plan's verification command `python3 scripts/setup.py --dry-run < /dev/null`
- All platform OAuth credentials are optional (blank to skip) so dev can start the stack with just DB/storage defaults
- Redirect URIs derived from BASE_URL at generation time to keep them in sync

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added stdin.isatty() guard to prompt() for non-interactive dry-run support**
- **Found during:** Task 1 (Create interactive setup script) — during verification
- **Issue:** `python3 scripts/setup.py --dry-run < /dev/null` raised `EOFError` because `input()` was called regardless of dry-run mode or stdin availability
- **Fix:** Added `if not sys.stdin.isatty(): return default` at the top of `prompt()`, and guarded the overwrite confirm and key-accept confirms with `sys.stdin.isatty()` checks
- **Files modified:** `scripts/setup.py`
- **Verification:** `python3 scripts/setup.py --dry-run < /dev/null` outputs full env content with all required vars
- **Committed in:** `ec3d0d1` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix — without it the plan's own verification command would fail. No scope creep.

## Issues Encountered

None beyond the stdin bug documented above.

## User Setup Required

None — no external service configuration required. Platform OAuth credentials (Meta, TikTok, Google, DV360) can be added later by re-running `make setup`.

## Next Phase Readiness

- Phase 01 (infrastructure portability) is fully complete: docker-compose stack, object storage layer, and developer onboarding all in place
- Any developer can now clone the repo and run `make dev` to get a working local stack
- Phase 02 (Security) and Phase 03 (BrainSuite Scoring) can proceed — the infrastructure foundation is solid

---
*Phase: 01-infrastructure-portability*
*Completed: 2026-03-20*
