import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.query.return_value = []
    mock.execute.return_value = None
    return mock


@pytest.fixture
def cache_service(mock_db):
    with patch("phinan.services.cache_service.get_database_manager") as mock_get_db:
        mock_get_db.return_value = mock_db

        from phinan.services.cache_service import CacheService

        CacheService._instance = None
        service = CacheService()
        yield service
        CacheService._instance = None


class TestCacheServiceGet:
    def test_get_returns_none_on_cache_miss(self, cache_service, mock_db):
        mock_db.query.return_value = []

        result = cache_service.get("AAPL", "ticker_info")

        assert result is None

    def test_get_returns_cached_data(self, cache_service, mock_db):
        cached_data = {"symbol": "AAPL", "name": "Apple Inc.", "current_price": 175.50}
        mock_db.query.return_value = [{"data": json.dumps(cached_data)}]

        result = cache_service.get("AAPL", "ticker_info")

        assert result == cached_data

    def test_get_normalizes_ticker_to_uppercase(self, cache_service, mock_db):
        mock_db.query.return_value = []

        cache_service.get("aapl", "ticker_info")

        call_args = mock_db.query.call_args[0]
        assert "AAPL" in call_args[1]

    def test_get_handles_already_parsed_json(self, cache_service, mock_db):
        cached_data = {"symbol": "AAPL"}
        mock_db.query.return_value = [{"data": cached_data}]

        result = cache_service.get("AAPL", "ticker_info")

        assert result == cached_data


class TestCacheServiceSet:
    def test_set_inserts_cache_entry(self, cache_service, mock_db):
        data = {"symbol": "AAPL", "current_price": 175.50}

        cache_service.set("AAPL", "ticker_info", data)

        mock_db.execute.assert_called_once()

    def test_set_uses_default_ttl(self, cache_service, mock_db):
        data = {"symbol": "AAPL"}

        cache_service.set("AAPL", "ticker_info", data)

        call_args = mock_db.execute.call_args[0]
        params = call_args[1]
        # params: (ticker_symbol, data_type, data, expires_at, cached_at)
        expires_at = params[3]
        cached_at = params[4]

        expected_ttl = timedelta(minutes=5)
        actual_ttl = expires_at - cached_at

        assert actual_ttl.total_seconds() == pytest.approx(
            expected_ttl.total_seconds(), rel=1
        )

    def test_set_accepts_custom_ttl(self, cache_service, mock_db):
        data = {"symbol": "AAPL"}

        cache_service.set("AAPL", "ticker_info", data, ttl_minutes=30)

        call_args = mock_db.execute.call_args[0]
        params = call_args[1]
        # params: (ticker_symbol, data_type, data, expires_at, cached_at)
        expires_at = params[3]
        cached_at = params[4]

        expected_ttl = timedelta(minutes=30)
        actual_ttl = expires_at - cached_at

        assert actual_ttl.total_seconds() == pytest.approx(
            expected_ttl.total_seconds(), rel=1
        )

    def test_set_serializes_dataclass(self, cache_service, mock_db):
        from dataclasses import dataclass

        @dataclass
        class TestData:
            symbol: str
            price: float

        data = TestData(symbol="AAPL", price=175.50)

        cache_service.set("AAPL", "ticker_info", data)

        call_args = mock_db.execute.call_args[0]
        params = call_args[1]
        # params: (ticker_symbol, data_type, data, expires_at, cached_at)
        json_data = json.loads(params[2])

        assert json_data["symbol"] == "AAPL"
        assert json_data["price"] == 175.50


class TestCacheServiceInvalidate:
    def test_invalidate_specific_type(self, cache_service, mock_db):
        cache_service.invalidate("AAPL", "ticker_info")

        call_args = mock_db.execute.call_args[0]
        assert "ticker_symbol = ?" in call_args[0]
        assert "data_type = ?" in call_args[0]

    def test_invalidate_all_types(self, cache_service, mock_db):
        cache_service.invalidate("AAPL")

        call_args = mock_db.execute.call_args[0]
        assert "ticker_symbol = ?" in call_args[0]
        assert "data_type" not in call_args[0]


class TestCacheServiceClearExpired:
    def test_clear_expired_removes_old_entries(self, cache_service, mock_db):
        cache_service.clear_expired()

        call_args = mock_db.execute.call_args[0]
        assert "expires_at < CURRENT_TIMESTAMP" in call_args[0]


class TestCacheServiceHealthCheck:
    def test_health_check_returns_true_when_db_accessible(self, cache_service, mock_db):
        mock_db.query.return_value = [{"1": 1}]

        assert cache_service.health_check() is True

    def test_health_check_returns_false_on_db_error(self, cache_service, mock_db):
        mock_db.query.side_effect = Exception("DB connection failed")

        assert cache_service.health_check() is False
