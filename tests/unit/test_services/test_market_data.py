from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from phinan.services.market_data import (
    MarketDataService,
    TickerInfo,
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


class TestYFinanceProviderOptions:
    def test_get_options_expirations_returns_ticker_expirations(
        self, yfinance_provider
    ):
        mock_ticker = MagicMock()
        mock_ticker.options = ["2026-07-17", "2026-08-21"]

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_options_expirations("AAPL")

        assert result == ["2026-07-17", "2026-08-21"]

    def test_get_options_chain_returns_calls_and_puts(self, yfinance_provider):
        calls = pd.DataFrame({"strike": [200.0]})
        puts = pd.DataFrame({"strike": [190.0]})
        mock_ticker = MagicMock()
        mock_ticker.option_chain.return_value.calls = calls
        mock_ticker.option_chain.return_value.puts = puts

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_options_chain("AAPL", "2026-07-17")

        assert result["calls"].equals(calls)
        assert result["puts"].equals(puts)
        mock_ticker.option_chain.assert_called_once_with("2026-07-17")


class TestYFinanceProviderAnalystDetails:
    def test_get_analyst_details_maps_yfinance_data(self, yfinance_provider):
        mock_ticker = MagicMock()
        mock_ticker.recommendations_summary = pd.DataFrame(
            [{"strongBuy": 5, "buy": 4, "hold": 3, "sell": 2, "strongSell": 1}]
        )
        mock_ticker.info = {
            "targetLowPrice": 170.0,
            "targetMeanPrice": 200.0,
            "targetMedianPrice": 198.0,
            "targetHighPrice": 225.0,
        }
        mock_ticker.upgrades_downgrades = pd.DataFrame(
            [
                {
                    "Firm": "Example Research",
                    "ToGrade": "Buy",
                    "FromGrade": "Hold",
                    "Action": "up",
                }
            ],
            index=[datetime(2026, 6, 20)],
        )

        with patch.object(yfinance_provider, "_get_yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            result = yfinance_provider.get_analyst_details("AAPL")

        assert result["recommendation_counts"]["strong_buy"] == 5
        assert result["price_targets"]["mean"] == 200.0
        assert result["recent_changes"][0]["firm"] == "Example Research"


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
            "phinan.services.market_data.service.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
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
            "phinan.services.market_data.service.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
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
            "phinan.services.market_data.service.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
                mock_settings.market_data.provider = "openbb"
                mock_settings.market_data.openbb_provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_primary
                service._fallback = mock_fallback

                result = service.get_ticker_info("AAPL")

        assert result.symbol == "AAPL"
        mock_fallback.get_ticker_info.assert_called_once_with("AAPL")


class TestMarketDataServiceCapabilities:
    def test_delegates_options_requests_to_options_provider(self, mock_cache):
        with patch(
            "phinan.services.market_data.service.get_cache_service",
            return_value=mock_cache,
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"
                service = MarketDataService()

        options_provider = MagicMock()
        options_provider.get_options_expirations.return_value = ["2026-07-17"]
        service._options_provider = options_provider

        result = service.get_options_expirations("AAPL")

        assert result == ["2026-07-17"]
        options_provider.get_options_expirations.assert_called_once_with("AAPL")

    def test_delegates_analyst_requests_to_analyst_provider(self, mock_cache):
        with patch(
            "phinan.services.market_data.service.get_cache_service",
            return_value=mock_cache,
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"
                service = MarketDataService()

        analyst_provider = MagicMock()
        analyst_provider.get_analyst_details.return_value = {
            "recommendation_counts": {},
            "price_targets": {},
            "recent_changes": [],
        }
        service._analyst_provider = analyst_provider

        result = service.get_analyst_details("AAPL")

        assert result["recent_changes"] == []
        analyst_provider.get_analyst_details.assert_called_once_with("AAPL")


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
            "phinan.services.market_data.service.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
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
            "phinan.services.market_data.service.get_cache_service", return_value=mock_cache
        ):
            with patch("phinan.services.market_data.service.settings") as mock_settings:
                mock_settings.market_data.provider = "yfinance"

                service = MarketDataService()
                service._primary = mock_provider

                result = service.get_price_range("INVALID")

        assert result is None
