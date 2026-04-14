---
status: awaiting_human_verify
trigger: "Clicking DV360 in Configuration/Platform Connections does nothing. Backend logs show a user lookup then ROLLBACK — no OAuth flow opens."
created: 2026-04-01T00:00:00Z
updated: 2026-04-01T00:00:00Z
symptoms_prefilled: true
---

## Current Focus
<!-- OVERWRITE on each update - reflects NOW -->

hypothesis: CONFIRMED — DV360 credentials never reach the Docker container because .env uses DV360_CLIENT_ID but docker-compose only passes DEV_DV360_CLIENT_ID, which is undefined. With CURRENT_ENV=development the settings validator promotes DEV_DV360_CLIENT_ID → DV360_CLIENT_ID, but DEV_DV360_CLIENT_ID is empty. DV360_CLIENT_ID ends up None → 503 HTTPException → get_db catches it → ROLLBACK.
test: n/a — root cause confirmed by env file inspection
expecting: n/a
next_action: rename DV360_CLIENT_ID → DEV_DV360_CLIENT_ID and DV360_CLIENT_SECRET → DEV_DV360_CLIENT_SECRET in .env to match the project's naming convention for dev credentials

## Symptoms
<!-- Written during gathering, then IMMUTABLE -->

expected: Clicking DV360 should open an OAuth flow (worked in the Replit version)
actual: Nothing happens in UI; backend logs show ROLLBACK immediately after user auth lookup
errors: |
  brainsuite_backend | ROLLBACK
  brainsuite_backend | INFO  [sqlalchemy.engine.Engine] ROLLBACK
  (Only a SELECT on users table is logged before the ROLLBACK — no INSERT/UPDATE, no explicit error message visible)
reproduction: Click DV360 tile in Configuration > Platform Connections
started: Worked in Replit version, never tested after local Docker migration — likely a migration/config issue

## Eliminated
<!-- APPEND only - prevents re-investigating -->

- hypothesis: Redis unavailable causing unhandled exception
  evidence: The ROLLBACK pattern occurs for ALL exceptions via get_db context manager; the 503 HTTPException path is more specific
  timestamp: 2026-04-01

- hypothesis: Missing DV360 backend route / broken import
  evidence: platforms.py has full DV360 handling at /oauth/init, /oauth/callback, /oauth/callback/dv360 — all present and correct
  timestamp: 2026-04-01

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-04-01
  checked: frontend/src/app/features/configuration/pages/platforms.component.ts
  found: startOAuth(platform) calls POST /platforms/oauth/init with {platform}; this calls the backend
  implication: Frontend is correct; issue is backend

- timestamp: 2026-04-01
  checked: backend/app/api/v1/endpoints/platforms.py:189-190
  found: if not settings.DV360_CLIENT_ID and payload.platform == "DV360": raise HTTPException(503)
  implication: If DV360_CLIENT_ID is None in the container, the 503 fires, which bubbles through get_db's except clause → ROLLBACK

- timestamp: 2026-04-01
  checked: backend/app/db/base.py:46-56
  found: get_db does rollback on ANY exception (including HTTPException) then re-raises
  implication: 503 HTTPException causes ROLLBACK log — this is why we see ROLLBACK but no explicit error (FastAPI handles HTTPException separately, the error response body is not logged at default level)

- timestamp: 2026-04-01
  checked: docker-compose.yml backend environment section (lines 92-130)
  found: DV360_CLIENT_ID and DV360_CLIENT_SECRET are COMPLETELY ABSENT from the docker-compose backend env block; no DV360 credentials are passed to the container at all
  implication: Container always starts with DV360_CLIENT_ID=None

- timestamp: 2026-04-01
  checked: .env file
  found: DV360_CLIENT_ID and DV360_CLIENT_SECRET defined at root level, but NOT as DEV_DV360_CLIENT_ID / DEV_DV360_CLIENT_SECRET
  implication: docker-compose.yml passes DEV_DV360_CLIENT_ID: ${DEV_DV360_CLIENT_ID:-} (line 125) which defaults to empty because DEV_DV360_CLIENT_ID is not in .env

- timestamp: 2026-04-01
  checked: backend/app/core/config.py apply_env_credentials validator
  found: When CURRENT_ENV=development, DEV_DV360_CLIENT_ID promotes to DV360_CLIENT_ID — but DEV_DV360_CLIENT_ID arrives as empty string
  implication: DV360_CLIENT_ID stays None → 503 on every DV360 connect attempt

- timestamp: 2026-04-01
  checked: .env GOOGLE_CLIENT_ID vs DEV_GOOGLE_CLIENT_ID pattern
  found: Google Ads has both GOOGLE_CLIENT_ID (production) and DEV_GOOGLE_CLIENT_ID (development). DV360 only has DV360_CLIENT_ID with no DEV_ variant.
  implication: DV360 was never correctly set up for the dev Docker environment

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause: DV360 credentials (DV360_CLIENT_ID, DV360_CLIENT_SECRET) are defined in .env without the DEV_ prefix required by the Docker dev workflow. docker-compose.yml passes DEV_DV360_CLIENT_ID and DEV_DV360_CLIENT_SECRET to the container (with empty defaults). CURRENT_ENV=development triggers the settings validator to promote DEV_DV360_CLIENT_ID → DV360_CLIENT_ID, but since DEV_DV360_CLIENT_ID is empty, DV360_CLIENT_ID remains None. The 503 HTTPException in init_oauth fires on every DV360 click, which propagates through get_db's exception handler causing the ROLLBACK log, and the 503 response body never makes it to the UI (frontend error handler silently clears the connecting state).
fix: Rename DV360_CLIENT_ID → DEV_DV360_CLIENT_ID and DV360_CLIENT_SECRET → DEV_DV360_CLIENT_SECRET in .env. This matches the project's naming convention for dev credentials and allows docker-compose to pass them correctly to the container.
verification: Fix applied — renamed DV360_CLIENT_ID → DEV_DV360_CLIENT_ID and DV360_CLIENT_SECRET → DEV_DV360_CLIENT_SECRET in .env. Data flow verified: docker-compose.yml passes DEV_DV360_CLIENT_ID to container; CURRENT_ENV=development causes settings validator to promote DEV_DV360_CLIENT_ID → DV360_CLIENT_ID; 503 check passes; dv360_oauth.generate_auth_url runs; OAuth popup opens. Awaiting container restart and human verification.
files_changed:
  - .env
