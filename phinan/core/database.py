"""Database manager for DuckDB with thread-safe connection handling.

Key patterns:
- Singleton manager with lazy initialization
- Shared connection (DuckDB handles concurrent reads internally)
- Write lock for serialized writes
- Context manager pattern for automatic cleanup
"""

import threading
import atexit
from contextlib import contextmanager
from typing import Generator, Optional

import duckdb

from ..config.settings import settings


class DatabaseManager:
    """Thread-safe DuckDB database manager.

    DuckDB allows multiple readers but only one writer at a time.
    This manager provides:
    - Shared connection (DuckDB Python API handles concurrent reads internally)
    - Write lock for serialized writes
    - Context manager pattern for automatic cleanup

    Note: DuckDB requires all connections to the same file use identical
    configuration (can't mix read_only=True with regular connections).
    """

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        """Singleton pattern for database manager."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize database manager."""
        # Use class lock to prevent race condition during initialization
        with self.__class__._lock:
            if self._initialized:
                return

            self._db_path = settings.database.resolved_path
            self._writer_conn: Optional[duckdb.DuckDBPyConnection] = None
            self._connection_lock = threading.Lock()
            self._writer_lock = threading.Lock()
            self._initialized = True

            # Ensure database directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            # Register cleanup on exit
            atexit.register(self._cleanup)

    def _cleanup(self):
        """Clean up connection on exit."""
        self.close()

    def close(self):
        """Close the underlying DuckDB connection and release its file lock.

        Required before forking/spawning a child Python process that will
        re-open the same database file - DuckDB only permits one read-write
        process per file, so the parent must drop its lock first.
        """
        with self._connection_lock:
            if self._writer_conn is not None:
                try:
                    self._writer_conn.close()
                except Exception:
                    pass
                self._writer_conn = None

    def _get_shared_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create the shared database connection.

        DuckDB requires all connections to use the same configuration.
        We use a single shared connection with cursor() for thread-safety.
        DuckDB's Python API handles concurrent access internally.
        """
        if self._writer_conn is None:
            with self._connection_lock:
                if self._writer_conn is None:
                    self._writer_conn = duckdb.connect(str(self._db_path))
                    # Configure memory limit for containerized environments
                    # DuckDB defaults to 80% of HOST RAM, not container limits
                    # This prevents OOMKilled errors in Docker/Railway
                    self._writer_conn.execute("SET memory_limit = '512MB'")
                    # Set threads to match container resources
                    self._writer_conn.execute("SET threads = 2")
        return self._writer_conn

    @contextmanager
    def get_connection(self, read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Get a database connection as context manager.

        Args:
            read_only: If True, acquires read lock (allows concurrent reads).
                      If False, acquires write lock (exclusive access for writes).

        Yields:
            DuckDB connection

        Note:
            DuckDB doesn't support mixing read_only and regular connections to
            the same file. Instead, we use a shared connection with appropriate
            locking: reads can proceed concurrently, writes are serialized.
        """
        if read_only:
            # For reads, we still use the shared connection but without
            # holding the writer lock - DuckDB handles read concurrency internally
            yield self._get_shared_connection()
        else:
            # Writer must hold lock for serialized writes
            with self._writer_lock:
                yield self._get_shared_connection()

    def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a write query.

        Returns None - the underlying cursor is closed before returning so
        callers cannot consume results. Use query()/query_df() for reads.
        """
        with self.get_connection() as conn:
            # cursor() creates an independent connection handle to the same
            # database. Required because callers may invoke this from worker
            # threads (e.g. via run_sync) while another thread holds the
            # parent. Wrap in `with` so the handle is closed on exit.
            with conn.cursor() as cursor:
                try:
                    cursor.execute(query, params)
                    cursor.commit()
                except Exception:
                    cursor.rollback()
                    raise

    def query(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute a read query and return results as list of dicts."""
        with self.get_connection(read_only=True) as conn:
            with conn.cursor() as cursor:
                result = cursor.execute(query, params)
                columns = [desc[0] for desc in result.description]
                return [dict(zip(columns, row)) for row in result.fetchall()]

    def query_df(self, query: str, params: tuple = ()):
        """Execute a read query and return as DataFrame."""
        with self.get_connection(read_only=True) as conn:
            with conn.cursor() as cursor:
                return cursor.execute(query, params).fetchdf()

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
