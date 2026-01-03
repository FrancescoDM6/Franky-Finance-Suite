#!/bin/sh
set -eu

if [ -z "${PORT:-}" ]; then
  echo "ERROR: PORT is not set; Caddy cannot bind to an empty port." >&2
  exit 1
fi

echo "Starting backend..."
python /app/scripts/start.py &
backend_pid=$!

echo "Starting Caddy on port ${PORT}..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
caddy_pid=$!

wait -n "$backend_pid" "$caddy_pid"
status=$?
echo "One process exited; shutting down (status=${status})." >&2
kill "$backend_pid" "$caddy_pid" 2>/dev/null || true
exit "$status"
