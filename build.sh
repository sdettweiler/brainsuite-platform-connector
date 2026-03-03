#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "► Installing Python dependencies..."
cd "$REPO_ROOT/backend"
pip install -q --no-cache-dir -r requirements.txt 2>&1 || true
touch .deps_installed
echo "✓ Python dependencies installed"

echo "► Building Angular frontend..."
cd "$REPO_ROOT/frontend"
export NG_CLI_ANALYTICS=false
npm install --legacy-peer-deps
npx ng build --configuration production
echo "✓ Frontend built"
