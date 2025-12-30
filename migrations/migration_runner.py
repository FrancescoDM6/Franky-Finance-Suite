"""
Database migration runner.

Applies SQL migrations in order and tracks applied versions.
"""
import sys
from pathlib import Path
import logging

# Add parent directory to path to import from phinan
sys.path.insert(0, str(Path(__file__).parent.parent))

from phinan.core.database import get_database_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MIGRATIONS_DIR = Path(__file__).parent


def get_pending_migrations(current_version: int) -> list[tuple[int, str, Path]]:
    """Get list of pending migrations."""
    migrations = []

    for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        # Parse version from filename (e.g., "001_initial_schema.sql" -> 1)
        try:
            version = int(migration_file.stem.split('_')[0])
            name = '_'.join(migration_file.stem.split('_')[1:])

            if version > current_version:
                migrations.append((version, name, migration_file))
        except (ValueError, IndexError):
            logger.warning(f"Skipping invalid migration filename: {migration_file}")

    return sorted(migrations, key=lambda x: x[0])


def run_migrations():
    """Run all pending migrations."""
    db = get_database_manager()

    # Ensure migrations table exists
    with db.get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    current_version = db.get_schema_version()
    logger.info(f"Current schema version: {current_version}")

    pending = get_pending_migrations(current_version)

    if not pending:
        logger.info("No pending migrations")
        return

    logger.info(f"Found {len(pending)} pending migrations")

    for version, name, migration_file in pending:
        logger.info(f"Applying migration {version}: {name}")

        try:
            # Read migration SQL
            sql = migration_file.read_text()

            # Execute migration
            db.execute_migration(sql)

            # Record migration
            db.record_migration(version, name)

            logger.info(f"Successfully applied migration {version}")

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise

    logger.info("All migrations applied successfully")


if __name__ == "__main__":
    run_migrations()
