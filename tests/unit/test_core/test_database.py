from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
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

            yield manager
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

            DatabaseManager._instance = None
