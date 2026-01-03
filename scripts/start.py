#!/usr/bin/env python3
"""Production startup script.

Runs database migrations before starting the Reflex app.
This ensures migrations run as an explicit deployment step,
not implicitly during request handling.
"""

import subprocess
import sys


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
    """Start Reflex in production mode."""
    print("Starting Reflex application...")
    cmd = [
        "reflex", "run",
        "--env", "prod",
        "--backend-host", "0.0.0.0"
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    run_migrations()
    start_reflex()
