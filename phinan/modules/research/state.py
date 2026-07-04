"""Research workflow state.

Owns the core research data vars (ticker, market data, analyst data, news,
charts, profile insights, synthesis) plus simple setters and child-state
clearing. Computed display vars live in display_vars.py mixins, the async
workflow orchestration lives in workflow.py (ResearchWorkflowMixin), and pure
computations live in research_logic.py.
"""

import logging
from typing import Any

import reflex as rx

from .display_vars import (
    AnalystVarsMixin,
    CoreVarsMixin,
    QualityVarsMixin,
    RangeVarsMixin,
    SentimentVarsMixin,
)
from .research_logic import compute_aggregate_sentiment, compute_quality_check
from .research_models import NewsItem
from .ticker_index import ticker_index
from .workflow import ResearchWorkflowMixin

logger = logging.getLogger(__name__)

# Re-exported for backward compatibility with callers that import NewsItem
# from this module.
__all__ = ["NewsItem", "ResearchState"]


class ResearchState(
    ResearchWorkflowMixin,
    CoreVarsMixin,
    AnalystVarsMixin,
    RangeVarsMixin,
    SentimentVarsMixin,
    QualityVarsMixin,
    rx.State,
):
    """State for the Research module.

    Handles:
    - Ticker lookup and data fetching
    - Quality assessment
    - Range analysis
    - News aggregation
    """

    # Input
    ticker_input: str = ""
    selected_ticker: str = ""
    range_period: str = "3mo"
    pending_ticker: str = ""  # Set by sidebar clicks, triggers search on page load

    # Loading states
    is_loading: bool = False
    loading_stage: str = ""
    error_message: str = ""

    # Backend-only: incremented on each research run so an in-flight run can
    # detect it was superseded by a newer search and stop writing state.
    _search_generation: int = 0

    # Results (dicts for Reflex serialization)
    ticker_info: dict[str, Any] = {}
    quality_check: dict[str, Any] = {}
    analyst_data: dict[str, Any] = {}
    price_range: dict[str, Any] = {}
    recent_news: list[NewsItem] = []

    # Aggregate sentiment for all news
    aggregate_sentiment: dict[
        str, Any
    ] = {}  # {dominant, counts, average_confidence, total}

    # Profile-aware insights
    profile_insights: list[str] = []

    # LLM synthesis
    llm_synthesis: str = ""
    is_generating_synthesis: bool = False
    synthesis_error: str = ""  # User-facing error when synthesis fails

    # Profile insights error
    profile_insights_error: str = ""  # User-facing error when insights fail

    # New: Tab and Chart state
    selected_tab: str = "overview"
    chart_period: str = "3mo"
    price_history: list[
        dict[str, Any]
    ] = []  # [{date, open, high, low, close, volume}, ...]


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if type(self) is ResearchState:
            self._load_tickers()

    def _load_tickers(self):
        """Ensure the shared ticker search index is loaded."""
        ticker_index.ensure_loaded()

    def set_selected_tab(self, tab: str):
        """Set the selected tab."""
        self.selected_tab = tab

    def set_ticker_input(self, value: str):
        """Update ticker input."""
        self.ticker_input = value.upper()
        self.error_message = ""

    def search_ticker(self, ticker: str):
        """Set pending ticker and redirect to research page.

        The actual search is triggered by check_pending_search on page load.
        """
        self.pending_ticker = ticker
        self.ticker_input = ticker
        self.is_loading = True
        self.loading_stage = "Navigating to Research..."
        return rx.redirect("/research")

    def set_range_period(self, period: str):
        """Set range period and refresh if ticker selected."""
        self.range_period = period
        if self.selected_ticker:
            return ResearchState.research_ticker

    def _compute_quality_check(self):
        """Compute quality assessment from ticker info."""
        self.quality_check = compute_quality_check(self.ticker_info)

    def _compute_aggregate_sentiment(self):
        """Compute aggregate sentiment across all news items."""
        self.aggregate_sentiment = compute_aggregate_sentiment(self.recent_news)

    async def clear_research(self):
        """Clear core Research state and both child states."""
        from .options_state import OptionsState
        from .volatility_state import VolatilityState

        options_state = await self.get_state(OptionsState)
        volatility_state = await self.get_state(VolatilityState)

        self.ticker_input = ""
        self.selected_ticker = ""
        self.ticker_info = {}
        self.quality_check = {}
        self.analyst_data = {}
        self.price_range = {}
        self.recent_news = []
        self.aggregate_sentiment = {}
        self.profile_insights = []
        self.llm_synthesis = ""
        self.price_history = []
        self.selected_tab = "overview"
        self.error_message = ""
        self.synthesis_error = ""
        self.profile_insights_error = ""

        options_state._reset_options()
        volatility_state._reset_volatility()
