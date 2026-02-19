#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Brainsuite Platform Connector — Replit startup script
# Single process: FastAPI serves both the API and the Angular SPA
# ─────────────────────────────────────────────────────────────────────────────
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
FRONTEND_DIST="$FRONTEND_DIR/dist/brainsuite-platform-connector/browser"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║    Brainsuite Platform Connector — Starting      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Detect & configure PostgreSQL ─────────────────────────────────────────
if [ -z "$DATABASE_URL" ]; then
  echo "❌ DATABASE_URL is not set."
  echo "   In Replit: open the Database tab and create a PostgreSQL database."
  echo "   The DATABASE_URL secret will be set automatically."
  exit 1
fi

# Convert postgres:// to postgresql+asyncpg:// for SQLAlchemy async
RAW_DB="$DATABASE_URL"
ASYNC_DB="${RAW_DB/postgres:\/\//postgresql+asyncpg://}"
ASYNC_DB="${ASYNC_DB/postgresql:\/\//postgresql+asyncpg://}"
export DATABASE_URL="$ASYNC_DB"
export SYNC_DATABASE_URL="${ASYNC_DB/+asyncpg/}"

echo "✓ Database configured"

# ── 2. Auto-configure secrets if not set ──────────────────────────────────────
if [ -z "$SECRET_KEY" ]; then
  echo "⚠  SECRET_KEY not set — generating one for this session."
  echo "   Add SECRET_KEY to Replit Secrets for a stable value."
  export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

if [ -z "$TOKEN_ENCRYPTION_KEY" ]; then
  export TOKEN_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

# ── 3. Auto-configure CORS for Replit domain ──────────────────────────────────
if [ -z "$BACKEND_CORS_ORIGINS" ]; then
  if [ -n "$REPLIT_DEV_DOMAIN" ]; then
    export BACKEND_CORS_ORIGINS='["https://'"$REPLIT_DEV_DOMAIN"'"]'
    echo "✓ CORS auto-configured for https://$REPLIT_DEV_DOMAIN"
  else
    export BACKEND_CORS_ORIGINS='["*"]'
    echo "⚠  BACKEND_CORS_ORIGINS not set — allowing all origins"
  fi
fi

echo "✓ Secrets configured"

# ── 4. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "► Installing Python dependencies..."
cd "$BACKEND_DIR"
pip install -q --no-cache-dir -r requirements.txt
echo "✓ Python dependencies ready"

# ── 5. Run database migrations ───────────────────────────────────────────────
echo ""
echo "► Running database migrations..."
alembic upgrade head
echo "✓ Database up to date"

# ── 6. Build Angular frontend if not already built ───────────────────────────
echo ""
if [ ! -f "$FRONTEND_DIST/index.html" ]; then
  echo "► Building Angular frontend (first run — ~4 minutes)..."
  cd "$FRONTEND_DIR"
  npm install --legacy-peer-deps --prefer-offline
  npm run build -- --configuration production
  if [ -f "$FRONTEND_DIST/index.html" ]; then
    echo "✓ Frontend built successfully"
  else
    echo "❌ Frontend build failed. Check the output above."
    exit 1
  fi
else
  echo "✓ Frontend already built  (delete frontend/dist/ to rebuild)"
fi

# ── 7. Launch ─────────────────────────────────────────────────────────────────
BACKEND_PORT="${PORT:-8000}"
REPL_URL="${REPLIT_DEV_DOMAIN:-localhost:$BACKEND_PORT}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  App:     https://$REPL_URL"
echo "  API:     https://$REPL_URL/api/v1/"
echo "  Health:  https://$REPL_URL/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BACKEND_DIR"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" \
  --workers 1 \
  --log-level info
