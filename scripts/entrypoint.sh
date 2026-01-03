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

# Wait for either process to exit (POSIX-compliant approach)
# Trap SIGTERM/SIGINT and forward to children
cleanup() {
  echo "Received signal, shutting down..."
  kill "$backend_pid" "$caddy_pid" 2>/dev/null || true
  exit 0
}
trap cleanup TERM INT

# Wait for both processes - if either exits, cleanup will trigger
wait "$backend_pid" "$caddy_pid"
status=$?
echo "Process exited (status=${status}), shutting down..." >&2
kill "$backend_pid" "$caddy_pid" 2>/dev/null || true
exit "$status"
