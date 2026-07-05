import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.query.return_value = []
    mock.execute.return_value = None
    return mock


@pytest.fixture
def mock_market_data():
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
    # Async version used by ResearchState._execute_research
    mock.get_ticker_info_async = AsyncMock(return_value=mock_info)

    mock_range = MagicMock()
    mock_range.period = "3mo"
    mock_range.high = 195.00
    mock_range.low = 165.00
    mock_range.current = 175.50
    mock_range.percent_of_range = 0.35
    mock.get_price_range.return_value = mock_range
    # Async version
    mock.get_price_range_async = AsyncMock(return_value=mock_range)

    analyst_details = {
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
        "recent_changes": [],
    }
    mock.get_analyst_details.return_value = analyst_details
    # Async version
    mock.get_analyst_details_async = AsyncMock(return_value=analyst_details)

    mock_news_item = MagicMock()
    mock_news_item.title = "Apple Reports Record Earnings"
    mock_news_item.publisher = "Reuters"
    mock_news_item.published = datetime.now()
    mock_news_item.link = "https://example.com/news/1"
    mock_news_item.summary = "Apple Inc reported record quarterly revenue."
    mock.get_news.return_value = [mock_news_item]
    # Async version
    mock.get_news_async = AsyncMock(return_value=[mock_news_item])

    mock.get_options_expirations.return_value = [
        "2025-02-21",
        "2025-03-21",
        "2025-04-18",
    ]
    mock.get_options_chain.return_value = {"calls": None, "puts": None}
    # Async versions
    mock.get_options_expirations_async = AsyncMock(return_value=["2025-02-21", "2025-03-21", "2025-04-18"])
    mock.get_options_chain_async = AsyncMock(return_value={"calls": None, "puts": None})

    import pandas as pd

    mock_df = pd.DataFrame(
        {
            "Open": [170.0, 172.0, 175.0],
            "High": [175.0, 178.0, 180.0],
            "Low": [168.0, 170.0, 173.0],
            "Close": [173.0, 176.0, 178.0],
            "Volume": [1000000, 1200000, 1100000],
        },
        index=pd.date_range("2025-01-01", periods=3, freq="D"),
    )
    mock.get_price_history.return_value = mock_df
    # Async version
    mock.get_price_history_async = AsyncMock(return_value=mock_df)

    return mock


@pytest.fixture
def mock_sentiment():
    mock = MagicMock()
    mock.health_check.return_value = True
    mock.score_batch.return_value = [
        {"label": "positive", "score": 0.85},
    ]
    return mock


@pytest.fixture
def mock_synthesis():
    mock = MagicMock()
    mock.health_check.return_value = False
    return mock


@pytest.fixture
def mock_volatility():
    mock = MagicMock()
    mock.health_check.return_value = False
    return mock


@pytest.fixture
def mock_user_context():
    mock = MagicMock()
    mock.active_profile = "standard"
    mock.watchlist = []
    return mock


@pytest.mark.integration
class TestResearchStateAsyncWorkflow:
    def test_research_ticker_sets_loading_state(
        self, mock_db, mock_market_data, mock_sentiment, mock_synthesis, mock_volatility
    ):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db
            mock_services.market_data = mock_market_data
            mock_services.sentiment = mock_sentiment
            mock_services.synthesis = mock_synthesis
            mock_services.volatility = mock_volatility

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "AAPL"

            gen = state.research_ticker()

            asyncio.run(gen.__anext__())

            assert state.is_loading is True
            assert state.loading_stage != ""

    def test_research_ticker_empty_input_sets_error(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = ""

            gen = state.research_ticker()

            try:
                asyncio.run(gen.__anext__())
            except StopAsyncIteration:
                pass

            assert state.error_message == "Please enter a ticker symbol"

    def test_research_ticker_invalid_ticker_sets_error(
        self, mock_db, mock_market_data, mock_sentiment, mock_synthesis
    ):
        with patch("phinan.services.services") as mock_services:
            mock_market_data.get_ticker_info.return_value = None
            mock_market_data.get_ticker_info_async = AsyncMock(return_value=None)
            mock_services.db = mock_db
            mock_services.market_data = mock_market_data
            mock_services.sentiment = mock_sentiment
            mock_services.synthesis = mock_synthesis

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_input = "INVALIDTICKER123"

            gen = state.research_ticker()

            async def exhaust_gen():
                async for _ in gen:
                    pass

            asyncio.run(exhaust_gen())

            assert "Could not find ticker" in state.error_message
            assert state.is_loading is False


@pytest.mark.integration
class TestResearchStateQualityCheck:
    def test_quality_check_high_pe_flag(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": 75.0,
                "profit_margin": 0.25,
                "debt_to_equity": 1.0,
                "dividend_yield": 0.04,
                "industry": "Technology",
            }

            state._compute_quality_check()

            assert "High P/E ratio (>50)" in state.quality_check.get("flags", [])

    def test_quality_check_negative_pe_flag(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": -5.0,
                "profit_margin": -0.10,
                "debt_to_equity": 1.0,
                "dividend_yield": 0.0,
                "industry": "Technology",
            }

            state._compute_quality_check()

            assert "Negative P/E (unprofitable)" in state.quality_check.get("flags", [])

    def test_quality_check_high_debt_flag(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": 20.0,
                "profit_margin": 0.15,
                "debt_to_equity": 3.5,
                "dividend_yield": 0.04,
                "industry": "Utilities",
            }

            state._compute_quality_check()

            assert "High debt/equity ratio (>2)" in state.quality_check.get("flags", [])

    def test_quality_check_low_dividend_flag(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": 20.0,
                "profit_margin": 0.15,
                "debt_to_equity": 1.0,
                "dividend_yield": 0.01,
                "industry": "Technology",
            }

            state._compute_quality_check()

            assert "Dividend below 3% margin target" in state.quality_check.get(
                "flags", []
            )

    def test_quality_check_overall_pass(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": 20.0,
                "profit_margin": 0.20,
                "debt_to_equity": 1.0,
                "dividend_yield": 0.05,
                "industry": "Technology",
            }

            state._compute_quality_check()

            assert state.quality_check.get("overall") == "Pass"
            assert len(state.quality_check.get("flags", [])) < 2

    def test_quality_check_overall_review_multiple_flags(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {
                "pe_ratio": 75.0,
                "profit_margin": 0.05,
                "debt_to_equity": 3.0,
                "dividend_yield": 0.01,
                "industry": "Technology",
            }

            state._compute_quality_check()

            assert state.quality_check.get("overall") == "Review"
            assert len(state.quality_check.get("flags", [])) >= 2


@pytest.mark.integration
class TestResearchStateAggregateSentiment:
    def test_aggregate_sentiment_positive_dominant(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState, NewsItem

            state = ResearchState()
            state.recent_news = [
                NewsItem(
                    title="Good news 1", sentiment_label="positive", sentiment_score=0.9
                ),
                NewsItem(
                    title="Good news 2",
                    sentiment_label="positive",
                    sentiment_score=0.85,
                ),
                NewsItem(
                    title="Bad news 1", sentiment_label="negative", sentiment_score=0.7
                ),
            ]

            state._compute_aggregate_sentiment()

            assert state.aggregate_sentiment.get("dominant") == "positive"
            assert state.aggregate_sentiment.get("counts", {}).get("positive") == 2
            assert state.aggregate_sentiment.get("counts", {}).get("negative") == 1
            assert state.aggregate_sentiment.get("total") == 3

    def test_aggregate_sentiment_negative_dominant(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState, NewsItem

            state = ResearchState()
            state.recent_news = [
                NewsItem(
                    title="Bad news 1", sentiment_label="negative", sentiment_score=0.9
                ),
                NewsItem(
                    title="Bad news 2", sentiment_label="negative", sentiment_score=0.85
                ),
                NewsItem(
                    title="Good news 1", sentiment_label="positive", sentiment_score=0.7
                ),
            ]

            state._compute_aggregate_sentiment()

            assert state.aggregate_sentiment.get("dominant") == "negative"
            assert state.aggregate_sentiment.get("counts", {}).get("negative") == 2

    def test_aggregate_sentiment_empty_news(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.recent_news = []

            state._compute_aggregate_sentiment()

            assert state.aggregate_sentiment == {}

    def test_aggregate_sentiment_average_confidence(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState, NewsItem

            state = ResearchState()
            state.recent_news = [
                NewsItem(
                    title="News 1", sentiment_label="positive", sentiment_score=0.80
                ),
                NewsItem(
                    title="News 2", sentiment_label="positive", sentiment_score=0.90
                ),
            ]

            state._compute_aggregate_sentiment()

            assert state.aggregate_sentiment.get("average_confidence") == 0.85


@pytest.mark.integration
class TestResearchStateClearResearch:
    def test_clear_research_resets_all_state_owners(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.options_state import OptionsState
            from phinan.modules.research.state import NewsItem, ResearchState
            from phinan.modules.research.volatility_state import VolatilityState
            from reflex.istate.manager.memory import StateManagerMemory

            async def run_clear():
                manager = StateManagerMemory.create(ResearchState.get_root_state())
                root = await manager.get_state("clear-test")
                state = root.get_substate(ResearchState.get_full_name().split("."))
                options_state = await state.get_state(OptionsState)
                volatility_state = await state.get_state(VolatilityState)

                state.ticker_input = "AAPL"
                state.selected_ticker = "AAPL"
                state.ticker_info = {"symbol": "AAPL"}
                state.quality_check = {"overall": "Pass"}
                state.recent_news = [NewsItem(title="Test")]
                options_state.options_calls = [{"strike": 175.0}]
                volatility_state.volatility_garch_vol = 0.25

                await state.clear_research()
                return state, options_state, volatility_state

            state, options_state, volatility_state = (
                asyncio.run(run_clear())
            )

            assert state.ticker_input == ""
            assert state.selected_ticker == ""
            assert state.ticker_info == {}
            assert state.quality_check == {}
            assert state.recent_news == []
            assert options_state.options_calls == []
            assert volatility_state.volatility_garch_vol == 0.0


@pytest.mark.integration
class TestResearchStateComputedVars:
    def test_upside_percentage_positive(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {"current_price": 100.0}
            state.analyst_data = {"target_price": 120.0}

            assert state.upside_percentage == 20

    def test_upside_percentage_negative(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {"current_price": 100.0}
            state.analyst_data = {"target_price": 80.0}

            assert state.upside_percentage == -20

    def test_upside_percentage_missing_data(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.ticker_info = {}
            state.analyst_data = {}

            assert state.upside_percentage == 0

    def test_range_position_near_high(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.price_range = {"percent_of_range": 0.85}

            assert state.range_position_label == "Near range high"
            assert state.range_position_color == "red"

    def test_range_position_near_low(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.price_range = {"percent_of_range": 0.15}

            assert state.range_position_label == "Near range low"
            assert state.range_position_color == "green"

    def test_range_position_mid_range(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.price_range = {"percent_of_range": 0.50}

            assert state.range_position_label == "Mid-range"
            assert state.range_position_color == "blue"

    def test_has_results_true(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.selected_ticker = "AAPL"
            state.ticker_info = {"symbol": "AAPL"}

            assert state.has_results is True

    def test_has_results_false(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.selected_ticker = ""
            state.ticker_info = {}

            assert state.has_results is False

    def test_total_analyst_recommendations(self, mock_db):
        with patch("phinan.services.services") as mock_services:
            mock_services.db = mock_db

            from phinan.modules.research.state import ResearchState

            state = ResearchState()
            state.analyst_data = {
                "recommendation_counts": {
                    "strong_buy": 10,
                    "buy": 15,
                    "hold": 5,
                    "sell": 2,
                    "strong_sell": 1,
                }
            }

            assert state.total_analyst_recommendations == 33
