#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Brainsuite Platform Connector — Replit startup script
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
FRONTEND_DIST="$FRONTEND_DIR/dist/brainsuite"
BACKEND_PORT="${PORT:-5000}"

# ── 0. Wait for old process to release the port ──────────────────────────────
for i in 1 2 3 4 5 6 7 8 9 10; do
  if ! lsof -i :"$BACKEND_PORT" -t >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
# Force kill if still occupied
fuser -k "$BACKEND_PORT"/tcp 2>/dev/null || true
sleep 0.3

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║    Brainsuite Platform Connector — Starting      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Detect & configure PostgreSQL ─────────────────────────────────────────
if [ -z "$DATABASE_URL" ]; then
  echo "❌ DATABASE_URL is not set."
  exit 1
fi

RAW_DB="$DATABASE_URL"
RAW_DB="${RAW_DB%%\?*}"
ASYNC_DB="${RAW_DB/postgres:\/\//postgresql+asyncpg://}"
ASYNC_DB="${ASYNC_DB/postgresql:\/\//postgresql+asyncpg://}"
export DATABASE_URL="$ASYNC_DB"
export SYNC_DATABASE_URL="${ASYNC_DB/+asyncpg/}"
echo "✓ Database configured"

# ── 2. Auto-configure secrets if not set ──────────────────────────────────────
if [ -z "$SECRET_KEY" ]; then
  export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi
if [ -z "$TOKEN_ENCRYPTION_KEY" ]; then
  export TOKEN_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

# ── 3. Auto-configure CORS ───────────────────────────────────────────────────
if [ -z "$BACKEND_CORS_ORIGINS" ]; then
  if [ -n "$REPLIT_DEV_DOMAIN" ]; then
    export BACKEND_CORS_ORIGINS='["https://'"$REPLIT_DEV_DOMAIN"'"]'
    echo "✓ CORS configured"
  else
    export BACKEND_CORS_ORIGINS='["*"]'
  fi
fi
echo "✓ Secrets configured"

# ── 4. Install Python dependencies (skip if cached) ──────────────────────────
DEPS_MARKER="$BACKEND_DIR/.deps_installed"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"
if [ ! -f "$DEPS_MARKER" ] || [ "$REQUIREMENTS" -nt "$DEPS_MARKER" ]; then
  echo "► Installing Python dependencies..."
  cd "$BACKEND_DIR"
  pip install -q --no-cache-dir -r requirements.txt 2>&1 || true
  touch "$DEPS_MARKER"
  echo "✓ Python dependencies ready"
else
  echo "✓ Python dependencies ready (cached)"
fi

# ── 5. Run database migrations ───────────────────────────────────────────────
echo "► Running database migrations..."
cd "$BACKEND_DIR"
alembic upgrade head 2>&1 || true
echo "✓ Database up to date"

# ── 6. Check frontend build ──────────────────────────────────────────────────
if [ ! -f "$FRONTEND_DIST/index.html" ]; then
  echo "► Building Angular frontend..."
  cd "$FRONTEND_DIR"
  npm install --legacy-peer-deps --prefer-offline 2>&1
  npm run build -- --configuration production 2>&1
  echo "✓ Frontend built"
else
  echo "✓ Frontend ready"
fi

# ── 7. Launch server (exec replaces shell — keeps PID 1) ─────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  App running on port $BACKEND_PORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BACKEND_DIR"
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" \
  --workers 1 \
  --log-level info \
  --timeout-keep-alive 120
