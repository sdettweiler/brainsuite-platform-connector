#!/bin/sh
set -e

# Start bgutil PO token provider in background (required for yt-dlp YouTube downloads).
# pip-installed bgutil-ytdlp-pot-provider places the binary at /usr/local/bin/bgutil.
bgutil --http --port 4416 &
BGUTIL_PID=$!

# Wait up to 15s for bgutil to accept connections before starting the main server.
echo "Waiting for bgutil to start on port 4416..."
i=0
while [ $i -lt 15 ]; do
    if curl -sf http://127.0.0.1:4416/ping >/dev/null 2>&1; then
        echo "bgutil ready"
        break
    fi
    i=$((i + 1))
    sleep 1
done
if [ $i -eq 15 ]; then
    echo "WARNING: bgutil did not start within 15s — video downloads may fail"
fi

# Run migrations then hand off to uvicorn (exec replaces the shell so SIGTERM propagates).
alembic upgrade heads && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
