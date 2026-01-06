from pathlib import Path
from typing import Generator

import duckdb
import pytest


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    cost_basis DECIMAL(18,2) NOT NULL,
    purchase_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_data_cache (
    id INTEGER PRIMARY KEY,
    ticker_symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,
    data JSON NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(ticker_symbol, data_type)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def in_memory_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    conn = duckdb.connect(":memory:")
    conn.execute(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_phinan.duckdb"


@pytest.fixture
def file_db(test_db_path: Path) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    conn = duckdb.connect(str(test_db_path))
    conn.execute(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def db_with_portfolio(
    in_memory_db: duckdb.DuckDBPyConnection,
) -> duckdb.DuckDBPyConnection:
    in_memory_db.execute("""
        INSERT INTO portfolio (id, ticker_symbol, quantity, cost_basis, purchase_date, notes)
        VALUES 
            (1, 'AAPL', 100, 150.00, '2024-01-01', 'Long-term hold'),
            (2, 'MSFT', 50, 380.00, '2024-02-15', 'Tech diversification'),
            (3, 'GOOGL', 25, 140.00, '2024-03-01', '')
    """)
    return in_memory_db


@pytest.fixture
def db_with_cache(in_memory_db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    import json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    future = now + timedelta(minutes=5)
    past = now - timedelta(minutes=5)

    in_memory_db.execute(
        """
        INSERT INTO market_data_cache (id, ticker_symbol, data_type, data, cached_at, expires_at)
        VALUES 
            (1, 'AAPL', 'ticker_info', ?, ?, ?),
            (2, 'MSFT', 'ticker_info', ?, ?, ?),
            (3, 'EXPIRED', 'ticker_info', ?, ?, ?)
    """,
        (
            json.dumps(
                {"symbol": "AAPL", "name": "Apple Inc.", "current_price": 175.50}
            ),
            now,
            future,
            json.dumps(
                {"symbol": "MSFT", "name": "Microsoft Corp.", "current_price": 400.00}
            ),
            now,
            future,
            json.dumps(
                {"symbol": "EXPIRED", "name": "Expired Entry", "current_price": 100.00}
            ),
            past - timedelta(minutes=10),
            past,
        ),
    )
    return in_memory_db
