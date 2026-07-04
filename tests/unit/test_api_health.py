"""Tests for health API status construction and special-case behavior."""

import sys
from datetime import datetime
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from phinan.api.health import (
    HEALTH_CHECK_TICKER,
    ServiceStatus,
    check_gemini,
    check_market_data,
    check_ollama,
    get_health_status,
)


@pytest.mark.unit
class TestHealthChecks:
    def test_market_data_uses_centralized_probe_ticker(self):
        with patch("phinan.services.services") as services:
            services.market_data.get_ticker_info.return_value = SimpleNamespace(
                current_price=201.5
            )

            status = check_market_data()

        services.market_data.get_ticker_info.assert_called_once_with(
            HEALTH_CHECK_TICKER
        )
        assert status.status == "healthy"
        assert status.details == {
            "provider": "yfinance",
            "test_ticker": HEALTH_CHECK_TICKER,
            "test_price": 201.5,
        }
        assert status.response_time_ms is not None

    def test_gemini_disabled_state_remains_untimed(self):
        settings = SimpleNamespace(
            gemini=SimpleNamespace(api_key="", model="gemini-test")
        )
        with patch("phinan.config.settings.settings", settings):
            status = check_gemini()

        assert status.status == "disabled"
        assert status.details == {"reason": "No API key configured"}
        assert status.response_time_ms is None

    def test_gemini_rate_limit_remains_degraded(self):
        fake_genai = ModuleType("google.genai")
        fake_genai.Client = MagicMock(
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
        )
        fake_google = ModuleType("google")
        fake_google.genai = fake_genai
        settings = SimpleNamespace(
            gemini=SimpleNamespace(api_key="test-key", model="gemini-test")
        )

        with (
            patch("phinan.config.settings.settings", settings),
            patch.dict(
                sys.modules,
                {"google": fake_google, "google.genai": fake_genai},
            ),
        ):
            status = check_gemini()

        assert status.status == "degraded"
        assert status.details == {"reason": "Rate limited"}
        assert status.error == "API rate limit reached"
        assert status.response_time_ms is not None

    def test_ollama_import_error_remains_untimed(self):
        with patch.dict(sys.modules, {"ollama": None}):
            status = check_ollama()

        assert status.status == "unhealthy"
        assert status.error == "ollama package not installed"
        assert status.response_time_ms is None

    def test_health_response_uses_timezone_aware_utc_timestamp(self):
        statuses = {
            "check_database": MagicMock(
                return_value=ServiceStatus(name="database", status="healthy")
            ),
            "check_gemini": MagicMock(
                return_value=ServiceStatus(name="gemini", status="healthy")
            ),
            "check_ollama": MagicMock(
                return_value=ServiceStatus(name="ollama", status="disabled")
            ),
            "check_market_data": MagicMock(
                return_value=ServiceStatus(name="market_data", status="healthy")
            ),
            "check_sentiment": MagicMock(
                return_value=ServiceStatus(name="sentiment", status="disabled")
            ),
            "check_volatility": MagicMock(
                return_value=ServiceStatus(name="volatility", status="disabled")
            ),
            "check_embeddings": MagicMock(
                return_value=ServiceStatus(name="embeddings", status="disabled")
            ),
        }

        with patch.multiple("phinan.api.health", **statuses):
            response = get_health_status()

        timestamp = datetime.fromisoformat(response.timestamp.replace("Z", "+00:00"))
        assert timestamp.tzinfo is not None
        assert timestamp.utcoffset().total_seconds() == 0
        assert response.status == "healthy"
        assert response.summary == {
            "healthy": 3,
            "unhealthy": 0,
            "degraded": 0,
            "disabled": 4,
        }
