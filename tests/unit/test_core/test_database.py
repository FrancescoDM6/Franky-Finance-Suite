import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest


class TestDatabaseManagerInitialization:
    def test_creates_database_directory_if_not_exists(self, tmp_path):
        db_path = tmp_path / "subdir" / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            assert db_path.parent.exists()
            manager.close()
            DatabaseManager._instance = None

    def test_singleton_pattern_returns_same_instance(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None

            manager1 = DatabaseManager()
            manager2 = DatabaseManager()

            assert manager1 is manager2
            manager1.close()
            DatabaseManager._instance = None


class TestDatabaseManagerQueries:
    @pytest.fixture
    def db_manager(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            with manager.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        value DECIMAL(10,2)
                    )
                """)

            try:
                yield manager
            finally:
                manager.close()
            DatabaseManager._instance = None

    def test_execute_inserts_data(self, db_manager):
        db_manager.execute(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            (1, "test", 100.50),
        )

        result = db_manager.query("SELECT * FROM test_table WHERE id = 1")

        assert len(result) == 1
        assert result[0]["name"] == "test"
        assert float(result[0]["value"]) == 100.50

    def test_query_returns_list_of_dicts(self, db_manager):
        db_manager.execute(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            (1, "first", 10.00),
        )
        db_manager.execute(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            (2, "second", 20.00),
        )

        result = db_manager.query("SELECT * FROM test_table ORDER BY id")

        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_query_df_returns_dataframe(self, db_manager):
        db_manager.execute(
            "INSERT INTO test_table (id, name, value) VALUES (?, ?, ?)",
            (1, "test", 100.00),
        )

        result = db_manager.query_df("SELECT * FROM test_table")

        assert not result.empty
        assert len(result) == 1


class TestDatabaseManagerHealthCheck:
    def test_health_check_returns_true_when_accessible(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            assert manager.health_check() is True
            manager.close()
            DatabaseManager._instance = None


class TestDatabaseManagerConnectionContext:
    def test_read_only_connection_allows_concurrent_access(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            with manager.get_connection(read_only=True) as conn1:
                with manager.get_connection(read_only=True) as conn2:
                    assert conn1 is conn2

            manager.close()
            DatabaseManager._instance = None

    def test_concurrent_first_reads_open_one_shared_connection(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            try:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [
                        executor.submit(manager.query, "SELECT 1 AS value")
                        for _ in range(8)
                    ]

                assert [future.result() for future in futures] == [
                    [{"value": 1}]
                    for _ in range(8)
                ]
            finally:
                manager.close()
                DatabaseManager._instance = None


class TestDatabaseManagerClose:
    def test_close_releases_file_lock_for_new_process(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            try:
                manager.execute("CREATE TABLE lock_test (id INTEGER)")
                manager.close()

                child_code = (
                    "import duckdb\n"
                    "import sys\n"
                    "conn = duckdb.connect(sys.argv[1])\n"
                    "conn.execute('SELECT 1')\n"
                    "conn.close()\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", child_code, str(db_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                assert result.returncode == 0, result.stderr or result.stdout
            finally:
                manager.close()
                DatabaseManager._instance = None

    def test_close_is_idempotent_and_reopens_on_next_query(self, tmp_path):
        db_path = tmp_path / "test.duckdb"

        with patch("phinan.core.database.settings") as mock_settings:
            mock_settings.database.resolved_path = db_path

            from phinan.core.database import DatabaseManager

            DatabaseManager._instance = None
            manager = DatabaseManager()

            try:
                manager.execute("CREATE TABLE reopen_test (id INTEGER)")
                manager.close()
                manager.close()

                manager.execute("INSERT INTO reopen_test (id) VALUES (?)", (1,))
                result = manager.query("SELECT id FROM reopen_test")

                assert result == [{"id": 1}]
            finally:
                manager.close()
                DatabaseManager._instance = None


class TestDatabaseSettings:
    def test_nested_database_path_env_var_is_supported(self, monkeypatch, tmp_path):
        db_path = tmp_path / "nested.duckdb"
        monkeypatch.setenv("PHINAN_DATABASE__PATH", str(db_path))
        monkeypatch.delenv("PHINAN_DATABASE_PATH", raising=False)

        from phinan.config.settings import Settings

        test_settings = Settings(_env_file=None)

        assert test_settings.database.resolved_path == db_path
