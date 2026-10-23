#!/bin/sh
set -e

echo "=========================================================="
echo "  Starting Prime Gate Antigravity Gateway (Container)    "
echo "=========================================================="

# Ensure data directory exists
mkdir -p /app/data

# Non-loopback check: ensure at least one active API key exists before binding to 0.0.0.0
# If none exists and HOST is 0.0.0.0, auto-generate bootstrap API key
python -c "
from prime_gate.db import db
try:
    keys = db.get_active_api_keys()
    if not keys:
        print('[BOOTSTRAP] No active API key found. Generating initial API key...')
        res = db.create_api_key(name='Docker Bootstrap Key')
        print('===================================================================')
        print('  BOOTSTRAP GATEWAY API KEY CREATED:')
        print('  ' + res['raw_key'])
        print('  Please save this key securely! It will not be shown again.')
        print('===================================================================')
except Exception as e:
    print('[BOOTSTRAP] Notice checking keys:', e)
"

# Launch Node.js Web UI in background
echo "[INIT] Launching Web UI dashboard on port ${UI_PORT:-52110}..."
node ui/server.js --port "${UI_PORT:-52110}" --api-port "${PORT:-52111}" &
UI_PID=$!

# Trap signals for graceful shutdown
cleanup() {
    echo "[SHUTDOWN] Stopping Prime Gate services..."
    kill -TERM "$UI_PID" 2>/dev/null || true
    wait "$UI_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Launch Python API Proxy in foreground
echo "[INIT] Launching Proxy Core on http://${HOST:-0.0.0.0}:${PORT:-52111}..."
exec python -m prime_gate.cli start --host "${HOST:-0.0.0.0}" --port "${PORT:-52111}"
