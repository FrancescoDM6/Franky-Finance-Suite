"""Database manager for DuckDB with thread-safe connection handling.

Key patterns:
- Singleton manager with lazy initialization
- Context-managed connections for automatic cleanup
- Separate read/write connection patterns for DuckDB's single-writer limitation
"""

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

import duckdb

from ..config.settings import settings


class DatabaseManager:
    """Thread-safe DuckDB database manager.

    DuckDB allows multiple readers but only one writer at a time.
    This manager provides:
    - Thread-local read connections for concurrent reads
    - Single writer connection with lock for serialized writes
    - Context manager pattern for automatic cleanup
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        """Singleton pattern for database manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize database manager."""
        if self._initialized:
            return

        self._db_path = settings.database.resolved_path
        self._writer_conn: Optional[duckdb.DuckDBPyConnection] = None
        self._writer_lock = threading.Lock()
        self._local = threading.local()
        self._initialized = True

        # Ensure database directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self, read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Get a database connection as context manager.

        Args:
            read_only: If True, uses thread-local read connection.
                      If False, uses the shared writer connection with lock.

        Yields:
            DuckDB connection
        """
        if read_only:
            # Thread-local read connection
            if not hasattr(self._local, "read_conn") or self._local.read_conn is None:
                self._local.read_conn = duckdb.connect(str(self._db_path), read_only=True)
            yield self._local.read_conn
        else:
            # Writer connection with lock
            with self._writer_lock:
                if self._writer_conn is None:
                    self._writer_conn = duckdb.connect(str(self._db_path))
                yield self._writer_conn

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a write query."""
        with self.get_connection() as conn:
            return conn.execute(query, params)

    def query(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute a read query and return results as list of dicts."""
        with self.get_connection(read_only=True) as conn:
            result = conn.execute(query, params)
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def query_df(self, query: str, params: tuple = ()):
        """Execute a read query and return as DataFrame."""
        with self.get_connection(read_only=True) as conn:
            return conn.execute(query, params).fetchdf()

    def get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            with self.get_connection(read_only=True) as conn:
                result = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
                ).fetchone()
                return result[0] if result else 0
        except Exception:
            return 0

    def execute_migration(self, sql: str):
        """Execute a migration SQL script."""
        with self.get_connection() as conn:
            conn.execute(sql)

    def record_migration(self, version: int, name: str):
        """Record a completed migration."""
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )

    def initialize_schema(self):
        """Initialize database schema from migration files."""
        from pathlib import Path

        migrations_dir = Path(__file__).parent.parent.parent / "migrations"

        if not migrations_dir.exists():
            return

        # Ensure migrations table exists
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        current_version = self.get_schema_version()

        # Find and apply pending migrations
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            try:
                version = int(migration_file.stem.split("_")[0])
                name = "_".join(migration_file.stem.split("_")[1:])

                if version > current_version:
                    sql = migration_file.read_text()
                    self.execute_migration(sql)
                    self.record_migration(version, name)
            except (ValueError, IndexError):
                continue

    def health_check(self) -> bool:
        """Check if database is accessible."""
        try:
            with self.get_connection(read_only=True) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False


# Global accessor
def get_database_manager() -> DatabaseManager:
    """Get the singleton database manager instance."""
    return DatabaseManager()
