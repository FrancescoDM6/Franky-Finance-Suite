"""E2E tests for the complete research workflow.

These tests simulate full user workflows through the research module,
mocking only external API calls while testing the integration of:
- ResearchState
- Market data service
- Sentiment service
- Synthesis service
- Caching
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_market_data_service():
    mock = MagicMock()

    mock_info = MagicMock()
    mock_info.symbol = "AAPL"
    mock_info.name = "Apple Inc."
    mock_info.sector = "Technology"
    mock_info.industry = "Consumer Electronics"
    mock_info.market_cap = 3000000000000
    mock_info.pe_ratio = 28.5
    mock_info.dividend_yield = 0.005
    mock_info.profit_margin = 0.25
    mock_info.debt_to_equity = 1.5
    mock_info.current_price = 175.50
    mock_info.analyst_rating = "buy"
    mock_info.target_price = 200.00
    mock_info.num_analysts = 40
    mock.get_ticker_info.return_value = mock_info

    mock_range = MagicMock()
    mock_range.period = "3mo"
    mock_range.high = 195.00
    mock_range.low = 165.00
    mock_range.current = 175.50
    mock_range.percent_of_range = 0.35
    mock.get_price_range.return_value = mock_range

    mock.get_analyst_details.return_value = {
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
            "high": 225.00,
        },
        "recent_changes": [],
    }

    mock_news = MagicMock()
    mock_news.title = "Apple Reports Strong Q4"
    mock_news.publisher = "Reuters"
    mock_news.published = datetime.now()
    mock_news.link = "https://example.com/news"
    mock_news.summary = "Apple Inc reported better than expected earnings."
    mock.get_news.return_value = [mock_news]

    mock.get_options_expirations.return_value = ["2025-02-21", "2025-03-21"]
    mock.get_options_chain.return_value = {"calls": None, "puts": None}

    import pandas as pd

    mock_history = pd.DataFrame(
        {
            "Open": [170.0, 172.0, 175.0],
            "High": [175.0, 178.0, 180.0],
            "Low": [168.0, 170.0, 173.0],
            "Close": [173.0, 176.0, 178.0],
            "Volume": [1000000, 1200000, 1100000],
        },
        index=pd.date_range("2025-01-01", periods=3, freq="D"),
    )
    mock.get_price_history.return_value = mock_history

    return mock


@pytest.fixture
def mock_sentiment_service():
    mock = MagicMock()
    mock.health_check.return_value = True
    mock.score_batch.return_value = [{"label": "positive", "score": 0.85}]
    return mock


@pytest.fixture
def mock_synthesis_service():
    mock = MagicMock()
    mock.health_check.return_value = False
    return mock


@pytest.fixture
def mock_volatility_service():
    mock = MagicMock()
    mock.health_check.return_value = False
    return mock


@pytest.fixture
def mock_user_context():
    mock = MagicMock()
    mock.active_profile = "franky"
    mock.watchlist = []
    return mock


@pytest.mark.e2e
class TestResearchWorkflowComplete:
    def test_full_research_flow_valid_ticker(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
        mock_user_context,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"
            assert state.ticker_info["symbol"] == "AAPL"
            assert state.ticker_info["current_price"] == 175.50
            assert state.price_range["high"] == 195.00
            assert state.is_loading is False
            assert state.error_message == ""

    def test_full_research_flow_invalid_ticker(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
    ):
        mock_market_data_service.get_ticker_info.return_value = None

        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "INVALIDTICKER"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert "Could not find ticker" in state.error_message
            assert state.is_loading is False

    def test_research_flow_populates_news_with_sentiment(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert len(state.recent_news) == 1
            assert state.recent_news[0].sentiment_label == "positive"
            assert state.recent_news[0].sentiment_score == 0.85

    def test_research_flow_computes_quality_check(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert "overall" in state.quality_check
            assert "flags" in state.quality_check

    def test_research_flow_fetches_price_history(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert len(state.price_history) == 3
            assert "date" in state.price_history[0]
            assert "close" in state.price_history[0]


@pytest.mark.e2e
class TestResearchWorkflowEdgeCases:
    def test_research_handles_sentiment_service_unavailable(
        self,
        mock_market_data_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        mock_sentiment = MagicMock()
        mock_sentiment.health_check.return_value = False

        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"
            assert state.is_loading is False
            assert len(state.recent_news) == 1
            assert state.recent_news[0].sentiment_label == "neutral"

    def test_research_handles_empty_news(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        mock_market_data_service.get_news.return_value = []

        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"
            assert len(state.recent_news) == 0
            assert state.aggregate_sentiment == {}

    def test_research_handles_autocomplete_format(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL - Apple Inc."

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"
            mock_market_data_service.get_ticker_info.assert_called_with("AAPL")


@pytest.mark.e2e
class TestResearchWorkflowStateManagement:
    def test_clear_research_resets_state(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"

            state.clear_research()

            assert state.ticker_input == ""
            assert state.selected_ticker == ""
            assert state.ticker_info == {}
            assert state.price_range == {}
            assert state.recent_news == []

    def test_consecutive_research_replaces_data(
        self,
        mock_market_data_service,
        mock_sentiment_service,
        mock_synthesis_service,
        mock_volatility_service,
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.market_data = mock_market_data_service
            mock_services.sentiment = mock_sentiment_service
            mock_services.synthesis = mock_synthesis_service
            mock_services.volatility = mock_volatility_service

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            import asyncio

            async def run_research():
                async for _ in state.research_ticker():
                    pass

            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "AAPL"

            mock_info_msft = MagicMock()
            mock_info_msft.symbol = "MSFT"
            mock_info_msft.name = "Microsoft Corporation"
            mock_info_msft.sector = "Technology"
            mock_info_msft.industry = "Software"
            mock_info_msft.market_cap = 2800000000000
            mock_info_msft.pe_ratio = 35.0
            mock_info_msft.dividend_yield = 0.008
            mock_info_msft.profit_margin = 0.35
            mock_info_msft.debt_to_equity = 0.5
            mock_info_msft.current_price = 400.00
            mock_info_msft.analyst_rating = "buy"
            mock_info_msft.target_price = 450.00
            mock_info_msft.num_analysts = 45
            mock_market_data_service.get_ticker_info.return_value = mock_info_msft

            state.ticker_input = "MSFT"
            asyncio.get_event_loop().run_until_complete(run_research())

            assert state.selected_ticker == "MSFT"
            assert state.ticker_info["symbol"] == "MSFT"
            assert state.ticker_info["current_price"] == 400.00
