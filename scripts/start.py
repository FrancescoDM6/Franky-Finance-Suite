#!/usr/bin/env python3
"""Production startup script.

Runs database migrations before starting the Reflex app.
This ensures migrations run as an explicit deployment step,
not implicitly during request handling.
"""

import os
import subprocess
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_migrations():
    """Run database migrations."""
    print("Running database migrations...")
    try:
        from phinan.core.database import get_database_manager

        db = get_database_manager()
        db.initialize_schema()
        print("Migrations completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


def start_reflex():
    """Start Reflex backend in production mode.

    Uses --backend-only to skip frontend compilation (already pre-built).
    Caddy serves static frontend and proxies backend routes.
    """
    # Backend always runs on 8000, Caddy proxies from PORT
    print("Starting Reflex backend on port 8000...")

    cmd = [
        "reflex", "run",
        "--env", "prod",
        "--backend-only",
        "--backend-host", "0.0.0.0",
        "--backend-port", "8000",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run_migrations()
    start_reflex()
