from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from phinan.services.market_data import (
    MarketDataService,
    TickerInfo,
    PriceRange,
    NewsItem,
    YFinanceProvider,
)


@pytest.fixture
def mock_cache():
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = None
    return mock


@pytest.fixture
def yfinance_provider():
    return YFinanceProvider()


class TestYFinanceProviderTickerInfo:
    def test_get_ticker_info_returns_ticker_info(self, yfinance_provider):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "longName": "Apple Inc.",
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

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_ticker_info("AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.sector == "Technology"
        assert result.current_price == 175.50

    def test_get_ticker_info_returns_none_for_invalid_ticker(self, yfinance_provider):
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_ticker_info("INVALID")

        assert result is None

    def test_get_ticker_info_handles_api_error(self, yfinance_provider):
        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.side_effect = Exception("API Error")

            result = yfinance_provider.get_ticker_info("AAPL")

        assert result is None


class TestYFinanceProviderPriceHistory:
    def test_get_price_history_returns_dataframe(self, yfinance_provider):
        mock_df = pd.DataFrame(
            {
                "Open": [170.0, 172.0],
                "High": [175.0, 176.0],
                "Low": [169.0, 171.0],
                "Close": [174.0, 175.0],
                "Volume": [1000000, 1100000],
            }
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_price_history("AAPL", "1mo")

        assert not result.empty
        assert len(result) == 2

    def test_get_price_history_returns_empty_on_error(self, yfinance_provider):
        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.side_effect = Exception("API Error")

            result = yfinance_provider.get_price_history("AAPL")

        assert result.empty


class TestYFinanceProviderNews:
    def test_get_news_returns_news_items(self, yfinance_provider):
        mock_news = [
            {
                "content": {
                    "title": "Apple Q4 Earnings",
                    "provider": {"displayName": "Reuters"},
                    "pubDate": "2024-01-15T10:00:00Z",
                    "canonicalUrl": {"url": "https://example.com/news"},
                    "summary": "Record earnings reported.",
                }
            }
        ]

        mock_ticker = MagicMock()
        mock_ticker.news = mock_news

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_news("AAPL", max_items=5)

        assert len(result) == 1
        assert result[0].title == "Apple Q4 Earnings"
        assert result[0].publisher == "Reuters"

    def test_get_news_returns_empty_on_no_news(self, yfinance_provider):
        mock_ticker = MagicMock()
        mock_ticker.news = None

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_news("AAPL")

        assert result == []


class TestMarketDataServiceCaching:
    def test_get_ticker_info_uses_cache(self, mock_cache):
        cached_data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 3000000000000,
            "pe_ratio": 28.5,
            "dividend_yield": 0.005,
            "profit_margin": 0.25,
            "debt_to_equity": 1.5,
            "analyst_rating": "buy",
            "target_price": 200.00,
            "num_analysts": 40,
            "current_price": 175.50,
        }
        mock_cache.get.return_value = cached_data

        with patch(
            "phinan.services.market_data.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"

                service = MarketDataService()
                result = service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        mock_cache.get.assert_called_once_with("AAPL", "ticker_info")

    def test_get_ticker_info_caches_fresh_data(self, mock_cache):
        mock_cache.get.return_value = None

        mock_provider = MagicMock()
        mock_provider.get_ticker_info.return_value = TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            current_price=175.50,
        )

        with patch(
            "phinan.services.market_data.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_provider

                service.get_ticker_info("AAPL")

        mock_cache.set.assert_called_once()


class TestMarketDataServiceFallback:
    def test_falls_back_to_yfinance_on_openbb_failure(self, mock_cache):
        mock_cache.get.return_value = None

        mock_primary = MagicMock()
        mock_primary.get_ticker_info.return_value = None

        mock_fallback = MagicMock()
        mock_fallback.get_ticker_info.return_value = TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            current_price=175.50,
        )

        with patch(
            "phinan.services.market_data.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.settings") as mock_settings:
                mock_settings.market_data.provider = "openbb"
                mock_settings.market_data.openbb_provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_primary
                service._fallback = mock_fallback

                result = service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        mock_fallback.get_ticker_info.assert_called_once_with("AAPL")


class TestPriceRangeCalculation:
    def test_get_price_range_calculates_correctly(self, mock_cache):
        mock_cache.get.return_value = None

        mock_df = pd.DataFrame(
            {
                "High": [180.0, 185.0, 190.0, 195.0],
                "Low": [165.0, 168.0, 170.0, 172.0],
                "Close": [175.0, 178.0, 182.0, 175.50],
            }
        )

        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = mock_df

        with patch(
            "phinan.services.market_data.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_provider

                result = service.get_price_range("AAPL", "3mo")

        assert result is not None
        assert result.high == 195.0
        assert result.low == 165.0
        assert result.current == 175.50
        assert 0 <= result.percent_of_range <= 1

    def test_get_price_range_returns_none_on_empty_history(self, mock_cache):
        mock_cache.get.return_value = None

        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = pd.DataFrame()

        with patch(
            "phinan.services.market_data.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_provider

                result = service.get_price_range("INVALID")

        assert result is None
