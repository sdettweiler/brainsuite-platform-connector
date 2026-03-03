#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$REPO_ROOT/frontend"
npm install --legacy-peer-deps
npx ng build --configuration production

cd "$REPO_ROOT/backend"
pip install -q --no-cache-dir -r requirements.txt
touch .deps_installed
