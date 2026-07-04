#!/usr/bin/env python3
"""Production startup script.

Runs database migrations before starting the Reflex app.
This ensures migrations run as an explicit deployment step,
not implicitly during request handling.
"""

import gc
import logging
import os
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log_memory_usage(label: str):
    """Log current memory usage for debugging."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = usage.ru_maxrss / 1024  # Convert to MB (Linux returns KB)
        logger.info("[MEMORY] %s: %.1f MB RSS", label, rss_mb)
    except Exception as e:
        logger.info("[MEMORY] %s: Unable to read (%s)", label, e)


def wait_for_private_network():
    """Wait for Railway's private network DNS to initialize.

    Railway's private network DNS resolver takes ~3 seconds to start.
    This is required for Redis and other internal service connections.
    """
    logger.info("Waiting for Railway private network DNS to initialize...")
    time.sleep(3)
    logger.info("Private network should be ready.")


def test_redis_connection():
    """Test Redis connectivity (optional, for debugging)."""
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            logger.info("Redis connected successfully at %s...", redis_url[:30])
        except Exception as e:
            logger.warning("Redis connection test failed: %s", e)
            logger.info("Continuing anyway - Reflex will retry...")
    else:
        logger.info("REDIS_URL not set - using disk state manager")


def run_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    db = None
    try:
        from phinan.core.database import get_database_manager

        db = get_database_manager()
        db.initialize_schema()
        # DuckDB only allows one read-write process per file. The Reflex
        # backend is spawned as a child process below and re-opens the same
        # database, so we must release this process's lock first.
        db.close()
        logger.info("Migrations completed successfully.")
    except Exception as e:
        logger.error("Migration failed: %s", e)
        sys.exit(1)
    finally:
        if db is not None:
            db.close()


def start_reflex():
    """Start Reflex backend in production mode.

    Uses 'reflex run --backend-only' to properly start the Reflex ASGI app.
    Direct uvicorn on rx.App() won't work - Reflex needs its runtime.
    Caddy serves static frontend and proxies backend routes.
    """
    # Debug: show what PORT Railway set
    port = os.environ.get("PORT", "NOT SET")
    logger.info("DEBUG: Railway PORT=%s", port)
    logger.info("DEBUG: Caddy should be listening on port %s", port)
    logger.info("DEBUG: Backend will run on port 8000")

    # Backend always runs on 8000, Caddy proxies from PORT
    logger.info("Starting Reflex backend on port 8000...")
    logger.info("DEBUG: Checking /srv contents:")
    subprocess.run(["ls", "-la", "/srv"], check=False)

    # Set environment for production
    env = os.environ.copy()
    env["REFLEX_ENV"] = "prod"
    # Tell Reflex to skip frontend compilation (already pre-built in Docker)
    env["__REFLEX_SKIP_COMPILE"] = "yes"
    # Force backend port
    env["REFLEX_BACKEND_PORT"] = "8000"

    logger.info(
        "DEBUG: Environment: %s",
        {
            k: v
            for k, v in env.items()
            if k
            in [
                "REFLEX_ENV",
                "PORT",
                "API_URL",
                "REDIS_URL",
                "REFLEX_BACKEND_PORT",
                "GRANIAN_WORKERS",
            ]
        },
    )

    # Use reflex run --backend-only instead of direct uvicorn
    # This properly initializes the Reflex runtime and creates the ASGI app
    cmd = [
        "reflex", "run",
        "--backend-only",
        "--env", "prod",
        "--backend-port", "8000",
        "--backend-host", "0.0.0.0",
    ]

    logger.info("DEBUG: Executing command: %s", " ".join(cmd))

    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    log_memory_usage("startup_begin")
    gc.collect()  # Clean up any startup garbage

    wait_for_private_network()
    log_memory_usage("after_network_wait")

    test_redis_connection()
    log_memory_usage("after_redis_test")

    run_migrations()
    log_memory_usage("after_migrations")

    gc.collect()  # Force GC before starting Reflex
    log_memory_usage("before_reflex_start")

    start_reflex()
