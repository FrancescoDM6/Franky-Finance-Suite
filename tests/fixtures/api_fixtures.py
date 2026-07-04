from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_gemini_success_response():
    mock_response = MagicMock()
    mock_response.text = "This is a test response from Gemini."
    return mock_response


@pytest.fixture
def mock_gemini_rate_limit_error():
    return Exception(
        "429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'RequestsPerDay'"
    )


@pytest.fixture
def mock_gemini_daily_quota_error():
    return Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for RequestsPerDay")


@pytest.fixture
def mock_gemini_minute_quota_error():
    return Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for RequestsPerMinute")


@pytest.fixture
def mock_ollama_success_response():
    return {
        "message": {
            "content": "This is a test response from Ollama.",
            "role": "assistant",
        },
        "model": "llama3.2:latest",
        "done": True,
    }


@pytest.fixture
def mock_ollama_with_tool_calls():
    return {
        "message": {
            "content": "",
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_stock_price",
                        "arguments": {"symbol": "AAPL"},
                    }
                }
            ],
        },
        "model": "llama3.2:latest",
        "done": True,
    }


@pytest.fixture
def mock_yfinance_ticker_info() -> dict[str, Any]:
    return {
        "longName": "Apple Inc.",
        "shortName": "Apple",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3000000000000,
        "trailingPE": 28.5,
        "dividendYield": 0.005,
        "profitMargins": 0.25,
        "debtToEquity": 150.0,
        "recommendationKey": "buy",
        "targetMeanPrice": 200.00,
        "numberOfAnalystOpinions": 40,
        "regularMarketPrice": 175.50,
    }


@pytest.fixture
def mock_yfinance_empty_info() -> dict[str, Any]:
    return {}


@pytest.fixture
def mock_yfinance_news() -> list[dict[str, Any]]:
    return [
        {
            "content": {
                "title": "Apple Reports Record Q4 Earnings",
                "provider": {"displayName": "Reuters"},
                "pubDate": "2024-01-15T10:00:00Z",
                "canonicalUrl": {"url": "https://example.com/news/1"},
                "summary": "Apple Inc reported record quarterly revenue.",
            }
        },
        {
            "content": {
                "title": "Apple Faces EU Regulatory Pressure",
                "provider": {"displayName": "Bloomberg"},
                "pubDate": "2024-01-14T14:30:00Z",
                "canonicalUrl": {"url": "https://example.com/news/2"},
                "summary": "European regulators investigating Apple.",
            }
        },
    ]


@pytest.fixture
def mock_finbert_positive_result():
    return {
        "label": "positive",
        "score": 0.92,
        "scores": {"positive": 0.92, "negative": 0.03, "neutral": 0.05},
        "source": "finbert",
    }


@pytest.fixture
def mock_finbert_negative_result():
    return {
        "label": "negative",
        "score": 0.87,
        "scores": {"positive": 0.05, "negative": 0.87, "neutral": 0.08},
        "source": "finbert",
    }


@pytest.fixture
def mock_finbert_low_confidence_result():
    return {
        "label": "neutral",
        "score": 0.45,
        "scores": {"positive": 0.30, "negative": 0.25, "neutral": 0.45},
        "source": "finbert",
    }


@pytest.fixture
def mock_llm_sentiment_fallback():
    return {
        "label": "positive",
        "score": 0.85,
        "reasoning": "Strong earnings indicate bullish momentum",
        "source": "llm",
    }
