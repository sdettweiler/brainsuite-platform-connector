#!/usr/bin/env bash
set -euo pipefail
# ─────────────────────────────────────────────────────────────────────────────
# Brainsuite Platform Connector — Replit startup script
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
FRONTEND_DIST="$FRONTEND_DIR/dist/brainsuite"
BACKEND_PORT=5000

export TZ="${TZ:-UTC}"

# ── 0. Ensure port 5000 is free ──────────────────────────────────────────────
cleanup_port() {
  local pids
  pids=$(lsof -ti :"$BACKEND_PORT" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "► Cleaning up port $BACKEND_PORT..."
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
    done
    sleep 1
    pids=$(lsof -ti :"$BACKEND_PORT" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      for pid in $pids; do
        kill -9 "$pid" 2>/dev/null || true
      done
      sleep 0.5
    fi
  fi
}
cleanup_port

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║    Brainsuite Platform Connector — Starting      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Detect & configure PostgreSQL ─────────────────────────────────────────
if [ -z "${DATABASE_URL:-}" ]; then
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

# ── 2. Auto-configure secrets if not set ─────────────────────────────────────
if [ -z "${SECRET_KEY:-}" ]; then
  export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi
if [ -z "${TOKEN_ENCRYPTION_KEY:-}" ]; then
  export TOKEN_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

# ── 3. Auto-configure CORS ──────────────────────────────────────────────────
if [ -z "${BACKEND_CORS_ORIGINS:-}" ]; then
  if [ -n "${REPLIT_DEV_DOMAIN:-}" ]; then
    export BACKEND_CORS_ORIGINS='["https://'"$REPLIT_DEV_DOMAIN"'"]'
    echo "✓ CORS configured"
  else
    export BACKEND_CORS_ORIGINS='["*"]'
  fi
fi
echo "✓ Secrets configured"

# ── 4. Install Python dependencies (skip if cached) ─────────────────────────
DEPS_MARKER="$BACKEND_DIR/.deps_installed"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"
if [ ! -f "$DEPS_MARKER" ] || [ "$REQUIREMENTS" -nt "$DEPS_MARKER" ]; then
  echo "► Installing Python dependencies..."
  cd "$BACKEND_DIR"
  if pip install -q --no-cache-dir -r requirements.txt 2>&1; then
    touch "$DEPS_MARKER"
    echo "✓ Python dependencies ready"
  else
    echo "⚠ pip install had errors (continuing anyway)"
  fi
else
  echo "✓ Python dependencies ready (cached)"
fi

# ── 5. Check frontend build ──────────────────────────────────────────────────
export NG_CLI_ANALYTICS=false
if [ ! -f "$FRONTEND_DIST/index.html" ]; then
  echo "► Building Angular frontend..."
  cd "$FRONTEND_DIR"
  npm install --legacy-peer-deps --prefer-offline 2>&1
  npm run build -- --configuration production 2>&1
  echo "✓ Frontend built"
else
  echo "✓ Frontend ready"
fi

# ── 6. Start temp health server, then launch uvicorn ─────────────────────────
HEALTH_PID_FILE="/tmp/brainsuite_health.pid"

python3 -c "
import http.server, socketserver, os, json

socketserver.TCPServer.allow_reuse_address = True

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'version': 'starting'}).encode())
    def log_message(self, *args):
        pass

s = socketserver.TCPServer(('0.0.0.0', $BACKEND_PORT), H)
with open('$HEALTH_PID_FILE', 'w') as f:
    f.write(str(os.getpid()))
s.serve_forever()
" &
sleep 0.3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  App running on port $BACKEND_PORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$BACKEND_DIR"
export BACKEND_PORT
exec python start_server.py
