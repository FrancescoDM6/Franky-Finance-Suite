import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "unit: Fast unit tests with no external dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that may use database or mocked APIs"
    )
    config.addinivalue_line("markers", "e2e: End-to-end workflow tests")
    config.addinivalue_line("markers", "slow: Slow tests (skip with -m 'not slow')")
    config.addinivalue_line("markers", "performance: Performance benchmark tests")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def mock_settings():
    with patch("phinan.config.settings.settings") as mock:
        mock.gemini.api_key = "test-api-key"
        mock.gemini.model = "gemini-2.0-flash-exp"
        mock.gemini.timeout = 60
        mock.ollama.base_url = "http://localhost:11434"
        mock.ollama.model = "llama3.2:latest"
        mock.ollama.timeout = 120
        mock.market_data.provider = "yfinance"
        mock.market_data.openbb_provider = "yfinance"
        mock.market_data.cache_ttl_minutes = 5
        mock.ai_services.sentiment_model = "yiyanghkust/finbert-tone"
        mock.ai_services.enable_sentiment = False
        yield mock


@pytest.fixture
def mock_service_registry():
    with patch("phinan.services.services") as mock_registry:
        mock_registry.llm = MagicMock()
        mock_registry.market_data = MagicMock()
        mock_registry.sentiment = MagicMock()
        mock_registry.synthesis = MagicMock()
        mock_registry.db = MagicMock()
        mock_registry.cache = MagicMock()
        mock_registry.volatility = MagicMock()
        yield mock_registry


@pytest.fixture
def sample_ticker_info() -> dict:
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 3000000000000,
        "pe_ratio": 28.5,
        "dividend_yield": 0.005,
        "profit_margin": 0.25,
        "debt_to_equity": 1.5,
        "current_price": 175.50,
        "analyst_rating": "buy",
        "target_price": 200.00,
        "num_analysts": 40,
    }


@pytest.fixture
def sample_news_items() -> list[dict]:
    return [
        {
            "title": "Apple Reports Record Q4 Earnings",
            "publisher": "Reuters",
            "published": "2024-01-15T10:00:00Z",
            "link": "https://example.com/news/1",
            "summary": "Apple Inc reported record quarterly revenue driven by iPhone sales.",
        },
        {
            "title": "Apple Faces Regulatory Pressure in EU",
            "publisher": "Bloomberg",
            "published": "2024-01-14T14:30:00Z",
            "link": "https://example.com/news/2",
            "summary": "European regulators are investigating Apple's App Store policies.",
        },
        {
            "title": "Apple Announces New Product Line",
            "publisher": "TechCrunch",
            "published": "2024-01-13T09:00:00Z",
            "link": "https://example.com/news/3",
            "summary": "Apple unveiled its latest product lineup at a special event.",
        },
    ]


@pytest.fixture
def sample_price_range() -> dict:
    return {
        "period": "3mo",
        "high": 195.00,
        "low": 165.00,
        "current": 175.50,
        "percent_of_range": 0.35,
    }


@pytest.fixture
def sample_analyst_data() -> dict:
    return {
        "rating": "buy",
        "target_price": 200.00,
        "num_analysts": 40,
        "recommendation_counts": {
            "strong_buy": 15,
            "buy": 18,
            "hold": 5,
            "sell": 2,
            "strong_sell": 0,
        },
        "price_targets": {
            "low": 160.00,
            "mean": 195.00,
            "median": 198.00,
            "high": 225.00,
        },
        "recent_changes": [
            {
                "date": "Jan 10",
                "firm": "Goldman Sachs",
                "to_grade": "Buy",
                "from_grade": "Hold",
                "action": "upgrade",
            },
            {
                "date": "Jan 08",
                "firm": "Morgan Stanley",
                "to_grade": "Overweight",
                "from_grade": "Equal-Weight",
                "action": "upgrade",
            },
        ],
    }


@pytest.fixture
def sample_portfolio_positions() -> list[dict]:
    return [
        {
            "id": 1,
            "ticker_symbol": "AAPL",
            "quantity": 100,
            "cost_basis": 150.00,
            "purchase_date": "2024-01-01",
            "notes": "Long-term hold",
        },
        {
            "id": 2,
            "ticker_symbol": "MSFT",
            "quantity": 50,
            "cost_basis": 380.00,
            "purchase_date": "2024-02-15",
            "notes": "Tech diversification",
        },
        {
            "id": 3,
            "ticker_symbol": "GOOGL",
            "quantity": 25,
            "cost_basis": 140.00,
            "purchase_date": "2024-03-01",
            "notes": "",
        },
    ]


@pytest.fixture
def sample_llm_response() -> dict:
    return {
        "content": "Based on the analysis, AAPL shows strong fundamentals with solid earnings growth.",
        "model": "gemini-2.0-flash-exp",
    }


@pytest.fixture
def sample_sentiment_result() -> dict:
    return {
        "label": "positive",
        "score": 0.85,
        "source": "finbert",
    }
