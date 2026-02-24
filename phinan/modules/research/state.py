"""Research module state.

Manages ticker research data, quality checks, and analysis.
"""

import reflex as rx
from typing import Any, Optional
from pydantic import BaseModel
from collections import OrderedDict
import time
import threading
import logging

logger = logging.getLogger(__name__)

# numpy imported lazily in calculate_volatility() to reduce startup memory

# Options cache TTL in seconds (5 minutes)
OPTIONS_CACHE_TTL = 300

# Maximum number of ticker:expiration pairs to cache (prevents unbounded memory growth)
OPTIONS_CACHE_MAX_SIZE = 100


class LRUCache:
    """Thread-safe LRU cache with TTL support for options data.

    Prevents unbounded memory growth by evicting least recently used entries
    when max_size is reached. Also evicts entries older than TTL.
    """

    def __init__(
        self, max_size: int = OPTIONS_CACHE_MAX_SIZE, ttl: int = OPTIONS_CACHE_TTL
    ):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[dict]:
        """Get item from cache, returns None if not found or expired."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry.get("timestamp", 0) > self._ttl:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.get("data")

    def set(self, key: str, data: Any) -> None:
        """Set item in cache, evicting LRU entries if needed."""
        with self._lock:
            # Remove if exists (will be re-added at end)
            if key in self._cache:
                del self._cache[key]

            # Evict oldest entries if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            # Add new entry
            self._cache[key] = {
                "data": data,
                "timestamp": time.time(),
            }

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)


# Global options cache (shared across state instances for efficiency)
_options_cache = LRUCache()


class TickerIndex:
    """Pre-built index for fast ticker search.

    Instead of O(n) linear search on every keystroke,
    uses a symbol prefix index for O(1) average lookup.
    """

    def __init__(self):
        self._tickers: list[dict] = []
        self._symbol_to_ticker: dict[str, dict] = {}
        self._symbols_sorted: list[str] = []
        self._name_words: dict[str, list[dict]] = {}  # word -> list of tickers
        self._initialized = False

    def build(self, tickers: list[dict]) -> None:
        """Build search indices from ticker list."""
        self._tickers = tickers
        self._symbol_to_ticker = {t["symbol"]: t for t in tickers}
        self._symbols_sorted = sorted(self._symbol_to_ticker.keys())

        # Build name word index for partial name search
        self._name_words.clear()
        for t in tickers:
            name_upper = t.get("name", "").upper()
            # Index each word in the name
            for word in name_upper.split():
                if len(word) >= 2:  # Only index words with 2+ chars
                    if word not in self._name_words:
                        self._name_words[word] = []
                    self._name_words[word].append(t)

        self._initialized = True

    def search(self, query: str, limit: int = 10) -> list[str]:
        """Fast search for tickers matching query.

        Returns list of "SYMBOL - Name" strings.
        """
        if not self._initialized or not query:
            return []

        query_upper = query.upper()
        results = []
        seen = set()

        # 1. Exact symbol match (highest priority)
        if query_upper in self._symbol_to_ticker:
            t = self._symbol_to_ticker[query_upper]
            results.append(f"{t['symbol']} - {t['name']}")
            seen.add(t["symbol"])

        # 2. Symbol prefix matches
        for symbol in self._symbols_sorted:
            if len(results) >= limit:
                break
            if symbol.startswith(query_upper) and symbol not in seen:
                t = self._symbol_to_ticker[symbol]
                results.append(f"{t['symbol']} - {t['name']}")
                seen.add(symbol)

        # 3. Symbol contains query (if still need more)
        if len(results) < limit:
            for symbol in self._symbols_sorted:
                if len(results) >= limit:
                    break
                if query_upper in symbol and symbol not in seen:
                    t = self._symbol_to_ticker[symbol]
                    results.append(f"{t['symbol']} - {t['name']}")
                    seen.add(symbol)

        # 4. Name word matches (if still need more)
        if len(results) < limit:
            # Find tickers where any word in name starts with query
            for word, tickers in self._name_words.items():
                if len(results) >= limit:
                    break
                if word.startswith(query_upper):
                    for t in tickers:
                        if len(results) >= limit:
                            break
                        if t["symbol"] not in seen:
                            results.append(f"{t['symbol']} - {t['name']}")
                            seen.add(t["symbol"])

        return results[:limit]

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Global ticker index (built once, shared across state instances)
_ticker_index = TickerIndex()


class NewsItem(BaseModel):
    """News item model for frontend. Uses pydantic.BaseModel."""

    title: str = ""
    publisher: str = ""
    published: str = ""
    link: str = ""  # URL to article
    sentiment_label: str = "neutral"  # "positive", "negative", "neutral"
    sentiment_score: float = 0.5  # 0-1 confidence
    sentiment_score_fmt: str = "50%"  # Formatted percentage string


class ResearchState(rx.State):
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

    # Results (dicts for Reflex serialization)
    ticker_info: dict[str, Any] = {}
    quality_check: dict[str, Any] = {}
    analyst_data: dict[str, Any] = {}
    price_range: dict[str, Any] = {}
    options_summary: str = ""

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

    @rx.var
    def safe_llm_synthesis(self) -> str:
        """Escape $ signs to prevent LaTeX math mode in markdown."""
        # Replace $ with escaped version to prevent math rendering
        return self.llm_synthesis.replace("$", "\\$")

    # New: Tab and Chart state
    selected_tab: str = "overview"
    chart_period: str = "3mo"
    price_history: list[
        dict[str, Any]
    ] = []  # [{date, open, high, low, close, volume}, ...]

    # Options Snapshot data
    options_expirations: list[str] = []  # ALL available expirations (no filtering)
    selected_expiration: str = ""  # Currently selected (profile sets default)
    options_calls: list[
        dict
    ] = []  # Filtered calls: {strike, bid, ask, oi, iv, annotation, is_atm}
    options_puts: list[dict] = []  # Filtered puts
    options_atm_iv: float = 0.0  # ATM implied volatility (decimal)
    options_days_to_expiry: int = 0  # Days until selected expiration
    options_loading: bool = False
    options_error: str = ""

    # Note: Options cache moved to module-level LRU cache (_options_cache)
    # for bounded memory usage and cross-instance sharing

    # Volatility Analysis data
    volatility_garch_vol: float = 0.0  # Annualized GARCH volatility (decimal)
    volatility_implied_vol: float = 0.0  # ATM IV (decimal)
    volatility_iv_garch_ratio: float = 0.0  # IV / GARCH ratio
    volatility_iv_garch_diff: float = 0.0  # IV - GARCH difference
    volatility_range_low: float = 0.0  # Expected range low price
    volatility_range_high: float = 0.0  # Expected range high price
    volatility_horizon: str = "21"  # Forecast horizon in days (string for select)
    volatility_available: bool = False  # Whether data is valid
    volatility_error: str = ""  # Error message if any
    volatility_loading: bool = False  # Loading state

    # Ticker Validation Data (kept for backwards compatibility, but index is preferred)
    tickers: list[dict] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_tickers()

    def _load_tickers(self):
        """Load tickers from JSON file and build search index."""
        import json
        import os

        # Use global index if already initialized (much faster)
        global _ticker_index
        if _ticker_index.is_initialized:
            return

        try:
            # Construct path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(current_dir, "data", "tickers.json")

            with open(data_path, "r") as f:
                tickers_data = json.load(f)

            # Build the global search index (O(n) once, then O(1) searches)
            _ticker_index.build(tickers_data)

            # Keep reference for backwards compatibility
            self.tickers = tickers_data

        except Exception as e:
            logger.error("Error loading tickers: %s", e)
            self.tickers = []

    @rx.var
    def ticker_options(self) -> list[str]:
        """Filter tickers based on input using pre-built index.

        Uses TickerIndex for O(1) average case instead of O(n) linear scan.
        """
        if not self.ticker_input:
            return []

        # Use the global pre-built index for fast search
        return _ticker_index.search(self.ticker_input, limit=10)

    @rx.var
    def has_results(self) -> bool:
        """Whether we have loaded results."""
        return bool(self.selected_ticker and self.ticker_info)

    @rx.var
    def current_price(self) -> Optional[float]:
        """Current price from ticker info."""
        return self.ticker_info.get("current_price")

    @rx.var
    def upside_percentage(self) -> int:
        """Calculate upside percentage to target (rounded integer)."""
        try:
            current = self.ticker_info.get("current_price")
            target = self.analyst_data.get("target_price")

            if not current or not target:
                return 0

            upside = ((float(target) / float(current)) - 1) * 100
            return int(round(upside))
        except Exception:
            return 0

    @rx.var
    def range_position_label(self) -> str:
        """Human-readable range position."""
        pct = self.price_range.get("percent_of_range", 0.5)
        if pct > 0.8:
            return "Near range high"
        elif pct < 0.2:
            return "Near range low"
        else:
            return "Mid-range"

    @rx.var
    def range_position_color(self) -> str:
        """Color scheme for range position."""
        pct = self.price_range.get("percent_of_range", 0.5)
        if pct > 0.8:
            return "red"
        elif pct < 0.2:
            return "green"
        else:
            return "blue"

    @rx.var
    def quality_overall(self) -> str:
        """Overall quality assessment."""
        return self.quality_check.get("overall", "N/A")

    @rx.var
    def quality_flags(self) -> list[str]:
        """Quality warning flags."""
        return self.quality_check.get("flags", [])

    @rx.var
    def has_chart_data(self) -> bool:
        """Whether we have chart data."""
        return len(self.price_history) > 0

    @rx.var
    def total_analyst_recommendations(self) -> int:
        """Total count of all analyst recommendations."""
        counts = self.analyst_data.get("recommendation_counts", {})
        return (
            counts.get("strong_buy", 0)
            + counts.get("buy", 0)
            + counts.get("hold", 0)
            + counts.get("sell", 0)
            + counts.get("strong_sell", 0)
        )

    @rx.var
    def rec_strong_buy(self) -> int:
        """Strong buy recommendation count."""
        return self.analyst_data.get("recommendation_counts", {}).get("strong_buy", 0)

    @rx.var
    def rec_buy(self) -> int:
        """Buy recommendation count."""
        return self.analyst_data.get("recommendation_counts", {}).get("buy", 0)

    @rx.var
    def rec_hold(self) -> int:
        """Hold recommendation count."""
        return self.analyst_data.get("recommendation_counts", {}).get("hold", 0)

    @rx.var
    def rec_sell(self) -> int:
        """Sell recommendation count."""
        return self.analyst_data.get("recommendation_counts", {}).get("sell", 0)

    @rx.var
    def rec_strong_sell(self) -> int:
        """Strong sell recommendation count."""
        return self.analyst_data.get("recommendation_counts", {}).get("strong_sell", 0)

    @rx.var
    def target_low(self) -> float:
        """Low analyst price target."""
        return self.analyst_data.get("price_targets", {}).get("low", 0) or 0

    @rx.var
    def target_mean(self) -> float:
        """Mean analyst price target."""
        return self.analyst_data.get("price_targets", {}).get("mean", 0) or 0

    @rx.var
    def target_high(self) -> float:
        """High analyst price target."""
        return self.analyst_data.get("price_targets", {}).get("high", 0) or 0

    @rx.var
    def recent_analyst_changes(self) -> list[dict]:
        """Recent analyst rating changes."""
        return self.analyst_data.get("recent_changes", [])

    @rx.var
    def fmt_target_low(self) -> str:
        """Formatted low analyst price target."""
        val = self.target_low
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_target_mean(self) -> str:
        """Formatted mean analyst price target."""
        val = self.target_mean
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_target_high(self) -> str:
        """Formatted high analyst price target."""
        val = self.target_high
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_range_high(self) -> str:
        """Formatted high price in range."""
        val = self.price_range.get("high")
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_range_low(self) -> str:
        """Formatted low price in range."""
        val = self.price_range.get("low")
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_range_current(self) -> str:
        """Formatted current price in range."""
        val = self.price_range.get("current")
        return f"{val:.2f}" if val else "N/A"

    @rx.var
    def fmt_range_percent(self) -> str:
        """Formatted percent of range."""
        val = self.price_range.get("percent_of_range")
        return f"{val * 100:.1f}%" if val is not None else "N/A"

    @rx.var
    def sentiment_counts(self) -> dict[str, int]:
        """Sentiment counts."""
        return self.aggregate_sentiment.get("counts", {})

    @rx.var
    def sentiment_positive_count(self) -> int:
        """Positive sentiment count."""
        return self.aggregate_sentiment.get("counts", {}).get("positive", 0)

    @rx.var
    def sentiment_neutral_count(self) -> int:
        """Neutral sentiment count."""
        return self.aggregate_sentiment.get("counts", {}).get("neutral", 0)

    @rx.var
    def sentiment_negative_count(self) -> int:
        """Negative sentiment count."""
        return self.aggregate_sentiment.get("counts", {}).get("negative", 0)

    @rx.var
    def sentiment_confidence_pct(self) -> int:
        """Average sentiment confidence percentage."""
        return int(self.aggregate_sentiment.get("average_confidence", 0) * 100)

    @rx.var
    def sentiment_total(self) -> int:
        """Total news analyzed."""
        return self.aggregate_sentiment.get("total", 0)

    @rx.var
    def options_atm_iv_pct(self) -> str:
        """ATM IV formatted as percentage."""
        return f"{self.options_atm_iv * 100:.1f}%" if self.options_atm_iv else "N/A"

    @rx.var
    def options_expiry_label(self) -> str:
        """Human-readable expiration label with days remaining."""
        if not self.selected_expiration:
            return "Select Expiration"
        return f"{self.selected_expiration} ({self.options_days_to_expiry}d)"

    @rx.var
    def has_options_data(self) -> bool:
        """Whether options data is loaded."""
        return len(self.options_calls) > 0 or len(self.options_puts) > 0

    @rx.var
    def is_near_range_high(self) -> bool:
        """True if current price is in upper 25% of range."""
        pct = self.price_range.get("percent_of_range", 0.5)
        return pct > 0.75 if pct is not None else False

    @rx.var
    def is_near_range_low(self) -> bool:
        """True if current price is in lower 25% of range."""
        pct = self.price_range.get("percent_of_range", 0.5)
        return pct < 0.25 if pct is not None else False

    # Volatility computed vars
    @rx.var
    def volatility_garch_vol_pct(self) -> str:
        """GARCH volatility formatted as percentage."""
        return (
            f"{self.volatility_garch_vol * 100:.1f}%"
            if self.volatility_garch_vol
            else "N/A"
        )

    @rx.var
    def volatility_implied_vol_pct(self) -> str:
        """Implied volatility formatted as percentage."""
        return (
            f"{self.volatility_implied_vol * 100:.1f}%"
            if self.volatility_implied_vol
            else "N/A"
        )

    @rx.var
    def volatility_iv_garch_ratio_fmt(self) -> str:
        """IV/GARCH ratio formatted."""
        return (
            f"{self.volatility_iv_garch_ratio:.2f}x"
            if self.volatility_iv_garch_ratio
            else "N/A"
        )

    @rx.var
    def volatility_iv_garch_diff_pct(self) -> str:
        """IV-GARCH difference formatted as percentage points."""
        if self.volatility_iv_garch_diff:
            sign = "+" if self.volatility_iv_garch_diff > 0 else ""
            return f"{sign}{self.volatility_iv_garch_diff * 100:.1f}pp"
        return "N/A"

    @rx.var
    def volatility_interpretation(self) -> str:
        """Human-readable interpretation of IV vs GARCH."""
        if not self.volatility_available or self.volatility_iv_garch_ratio == 0:
            return ""
        if self.volatility_iv_garch_ratio > 1.15:
            return "IV premium - options may be expensive"
        elif self.volatility_iv_garch_ratio < 0.85:
            return "IV discount - options may be cheap"
        else:
            return "IV near fair value"

    @rx.var
    def volatility_interpretation_color(self) -> str:
        """Color scheme for volatility interpretation."""
        if not self.volatility_available or self.volatility_iv_garch_ratio == 0:
            return "gray"
        if self.volatility_iv_garch_ratio > 1.15:
            return "amber"  # Expensive
        elif self.volatility_iv_garch_ratio < 0.85:
            return "green"  # Cheap
        else:
            return "blue"  # Fair

    @rx.var
    def volatility_horizon_label(self) -> str:
        """Human-readable horizon label."""
        horizon_map = {"5": "1 Week", "21": "1 Month", "63": "3 Months"}
        return horizon_map.get(self.volatility_horizon, "1 Month")

    @rx.var
    def fmt_pe_ratio(self) -> str:
        """Formatted P/E ratio."""
        val = self.ticker_info.get("pe_ratio")
        return f"{val:.2f}" if val is not None else "N/A"

    @rx.var
    def fmt_profit_margin(self) -> str:
        """Formatted profit margin."""
        val = self.ticker_info.get("profit_margin")
        return f"{val * 100:.1f}%" if val is not None else "N/A"

    @rx.var
    def fmt_debt_to_equity(self) -> str:
        """Formatted debt to equity."""
        val = self.ticker_info.get("debt_to_equity")
        return f"{val:.2f}" if val is not None else "N/A"

    @rx.var
    def fmt_dividend_yield(self) -> str:
        """Formatted dividend yield."""
        val = self.ticker_info.get("dividend_yield")
        return f"{val * 100:.2f}%" if val is not None else "N/A"

    async def handle_search_key(self, key: str):
        """Handle key press in search input - trigger search on Enter."""
        if key == "Enter":
            async for _ in self.research_ticker():
                yield  # Yield each step to update UI

    def set_selected_tab(self, tab: str):
        """Set the selected tab."""
        self.selected_tab = tab

    async def add_to_watchlist(self):
        """Add current ticker to user's watchlist."""
        from ...state.user_context import UserContextState

        if self.selected_ticker:
            user_ctx = await self.get_state(UserContextState)
            user_ctx.add_to_watchlist(self.selected_ticker)

    async def set_chart_period(self, period: str):
        """Set chart period and refresh chart data."""
        self.chart_period = period
        if self.selected_ticker:
            await self._fetch_price_history()

    async def set_options_expiration(self, expiration: str):
        """Handler for expiration dropdown change."""
        self.selected_expiration = expiration
        await self._load_options_for_expiration()

    def set_ticker_input(self, value: str):
        """Update ticker input."""
        self.ticker_input = value.upper()

    def search_ticker(self, ticker: str):
        """Set pending ticker and redirect to research page.

        The actual search is triggered by check_pending_search on page load.
        """
        self.pending_ticker = ticker
        self.ticker_input = ticker
        self.is_loading = True
        self.loading_stage = "Navigating to Research..."
        return rx.redirect("/research")

    async def check_pending_search(self):
        """Called on research page load - triggers search if pending."""
        if self.pending_ticker:
            # Clear pending and run the search
            ticker = self.pending_ticker
            self.pending_ticker = ""
            self.ticker_input = ticker
            self.is_loading = True
            self.loading_stage = "Fetching Market Data..."
            self.error_message = ""
            yield
            async for _ in self._execute_research():
                yield

    def set_range_period(self, period: str):
        """Set range period and refresh if ticker selected."""
        self.range_period = period
        if self.selected_ticker:
            return ResearchState.research_ticker

    async def research_ticker(self):
        """Research a ticker - main action."""
        if not self.ticker_input.strip():
            self.error_message = "Please enter a ticker symbol"
            return

        # Set loading state immediately
        self.is_loading = True
        self.loading_stage = "Fetching Market Data..."
        self.error_message = ""

        # Yield immediately to show loading state
        yield

        # Execute the actual research
        async for _ in self._execute_research():
            yield

    async def _execute_research(self):
        import asyncio
        import time
        from ...core.async_utils import run_sync
        from ...core.metrics import metrics, record_error

        start_time = time.perf_counter()
        raw_input = self.ticker_input.strip().upper()
        ticker_to_lookup = (
            raw_input.split(" - ")[0] if " - " in raw_input else raw_input
        )

        try:
            from ...services import services

            metrics.active_research_sessions.inc()

            info = await services.market_data.get_ticker_info_async(ticker_to_lookup)

            if not info:
                self.error_message = f"Could not find ticker: {ticker_to_lookup}. Try using the stock symbol (e.g., NFLX for Netflix)."
                self.is_loading = False
                self.loading_stage = ""
                return

            self.selected_ticker = ticker_to_lookup

            self.ticker_info = {
                "symbol": info.symbol,
                "name": info.name,
                "sector": info.sector,
                "industry": info.industry,
                "market_cap": info.market_cap,
                "pe_ratio": info.pe_ratio,
                "dividend_yield": info.dividend_yield,
                "profit_margin": info.profit_margin,
                "debt_to_equity": info.debt_to_equity,
                "current_price": info.current_price,
            }

            self.analyst_data = {
                "rating": info.analyst_rating,
                "target_price": info.target_price,
                "num_analysts": info.num_analysts,
                "recommendation_counts": {},
                "price_targets": {},
                "recent_changes": [],
            }

            self.loading_stage = "Fetching Market Data..."
            yield

            # Use TaskGroup for structured concurrency (fail-fast, automatic cleanup)
            async with asyncio.TaskGroup() as tg:
                analyst_task = tg.create_task(
                    services.market_data.get_analyst_details_async(ticker_to_lookup)
                )
                range_task = tg.create_task(
                    services.market_data.get_price_range_async(
                        self.selected_ticker, self.range_period
                    )
                )
                news_task = tg.create_task(
                    services.market_data.get_news_async(self.selected_ticker, max_items=20)
                )

            analyst_details = analyst_task.result()
            range_data = range_task.result()
            news_items = news_task.result()

            if analyst_details:
                self.analyst_data["recommendation_counts"] = analyst_details.get(
                    "recommendation_counts", {}
                )
                self.analyst_data["price_targets"] = analyst_details.get(
                    "price_targets", {}
                )
                self.analyst_data["recent_changes"] = analyst_details.get(
                    "recent_changes", []
                )

            if range_data:
                self.price_range = {
                    "period": range_data.period,
                    "high": range_data.high,
                    "low": range_data.low,
                    "current": range_data.current,
                    "percent_of_range": range_data.percent_of_range,
                }

            self.loading_stage = "Analyzing Sentiment..."
            yield

            sentiment_scores = []
            if news_items and services.sentiment.health_check():
                texts_to_analyze = [
                    f"{item.title}. {item.summary}" for item in news_items
                ]
                sentiment_scores = await run_sync(
                    services.sentiment.score_batch, texts_to_analyze
                )

            self.recent_news = []
            for i, item in enumerate(news_items or []):
                sentiment = sentiment_scores[i] if i < len(sentiment_scores) else {}
                self.recent_news.append(
                    NewsItem(
                        title=item.title,
                        publisher=item.publisher,
                        published=item.published.isoformat(),
                        link=item.link,
                        sentiment_label=sentiment.get("label", "neutral"),
                        sentiment_score=sentiment.get("score", 0.5),
                        sentiment_score_fmt=f"{sentiment.get('score', 0.5) * 100:.0f}%",
                    )
                )

            self._compute_aggregate_sentiment()
            self._compute_quality_check()

            self.loading_stage = "Loading Options & Charts..."
            yield

            # Fetch options data first (accesses UserContextState, must be sequential)
            await self._fetch_options_data()

            # Use TaskGroup for remaining concurrent tasks
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._fetch_volatility_data_safe())
                tg.create_task(self._fetch_price_history())
            yield

            self.loading_stage = "Generating AI Synthesis..."
            yield

            await self._apply_profile_insights()
            await self._generate_synthesis()
            yield

        except Exception as e:
            self.error_message = f"Error: {str(e)}"
            record_error("research", type(e).__name__)
        finally:
            duration = time.perf_counter() - start_time
            metrics.research_duration.labels(ticker=ticker_to_lookup).observe(duration)
            metrics.active_research_sessions.dec()
            self.is_loading = False
            self.loading_stage = ""

    async def _fetch_volatility_data_safe(self):
        try:
            await self._fetch_volatility_data()
        except Exception as e:
            self.volatility_error = str(e)
            self.volatility_available = False

    async def _generate_synthesis(self, force_refresh: bool = False):
        """Generate LLM synthesis of the research data.

        Args:
            force_refresh: If True, bypass cache and regenerate synthesis
        """
        from ...services import services
        from ...services.synthesis import ResearchContext
        from ...state.user_context import UserContextState
        from .profiles import get_profile

        # Check if synthesis service is available
        if not services.synthesis.health_check():
            self.llm_synthesis = ""
            self.synthesis_error = "AI analysis unavailable: service offline"
            logger.warning(
                "Synthesis service health check failed for %s", self.selected_ticker
            )
            return

        try:
            self.is_generating_synthesis = True

            # Get user profile
            user_ctx = await self.get_state(UserContextState)
            profile = get_profile(user_ctx.active_profile)

            # Get portfolio position if user owns this stock
            portfolio_position = None
            try:
                from ..portfolio.state import PortfolioState

                portfolio_state = await self.get_state(PortfolioState)
                pos = portfolio_state.get_position_for_ticker(self.selected_ticker)
                if pos:
                    portfolio_position = {
                        "quantity": pos.quantity,
                        "cost_basis": pos.cost_basis,
                        "current_price": pos.current_price,
                        "gain_loss_percent": pos.gain_loss_percent,
                    }
            except Exception as e:
                logger.warning("Could not fetch portfolio context: %s", e)

            # Determine aggregate news sentiment
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for item in self.recent_news:
                sentiment_counts[item.sentiment_label] = (
                    sentiment_counts.get(item.sentiment_label, 0) + 1
                )
            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)

            # Build context and generate synthesis via service
            context = ResearchContext(
                ticker=self.selected_ticker,
                ticker_info=self.ticker_info,
                price_range=self.price_range,
                analyst_data=self.analyst_data,
                quality_check=self.quality_check,
                news_sentiment=dominant_sentiment.title(),
                profile_name=profile.name,
                profile_description=profile.description,
                timeframe=profile.typical_timeframe,
                default_range=profile.default_range_period,
                portfolio_position=portfolio_position,
                options_summary=self.options_summary,
                options_expiration=self.selected_expiration,
            )

            result = await services.synthesis.generate_research_synthesis_async(
                context, force_refresh=force_refresh
            )

            if result.success:
                self.llm_synthesis = result.content
            else:
                self.llm_synthesis = ""

        except Exception as e:
            logger.error(
                "Error generating synthesis for %s: %s", self.selected_ticker, e
            )
            self.llm_synthesis = ""
            self.synthesis_error = "AI analysis failed: please try again"
        finally:
            self.is_generating_synthesis = False

    async def refresh_synthesis(self):
        """Manually refresh the AI synthesis (bypasses cache)."""
        if not self.selected_ticker:
            return
        await self._generate_synthesis(force_refresh=True)

    async def _apply_profile_insights(self):
        """Generate profile-specific insights based on active user profile."""
        from ...state.user_context import UserContextState
        from .profiles import get_conservative_insights, get_aggressive_insights, get_standard_insights

        try:
            # Get user context state to find active profile
            user_ctx = await self.get_state(UserContextState)
            profile = user_ctx.active_profile.lower()

            # Convert NewsItem objects to dicts for insight functions
            news_dicts = [
                {"title": n.title, "publisher": n.publisher} for n in self.recent_news
            ]

            if profile == "conservative":
                self.profile_insights = get_conservative_insights(
                    self.ticker_info, self.price_range, self.analyst_data
                )
            elif profile == "aggressive":
                self.profile_insights = get_aggressive_insights(
                    self.ticker_info, self.price_range, news_dicts, self.analyst_data
                )
            else:
                # Standard or default
                self.profile_insights = get_standard_insights(
                    self.ticker_info, self.price_range, news_dicts, self.analyst_data
                )
        except Exception as e:
            logger.error("Error generating profile insights: %s", e)
            self.profile_insights = []
            self.profile_insights_error = "Insights unavailable"

    async def _fetch_price_history(self):
        """Fetch price history for charts."""
        if not self.selected_ticker:
            return

        try:
            from ...services import services

            df = services.market_data.get_price_history(
                self.selected_ticker, period=self.chart_period, interval="1d"
            )

            if df.empty:
                self.price_history = []
                return

            # Case-insensitive column access
            col_map = {c.lower(): c for c in df.columns}
            close_col = col_map.get("close")

            if not close_col:
                self.price_history = []
                return

            # Convert DataFrame to list of dicts for Reflex
            # Only store date and close - the only fields used by the chart
            history_data = []
            for idx, row in df.iterrows():
                history_data.append(
                    {
                        "date": idx.strftime("%Y-%m-%d")
                        if hasattr(idx, "strftime")
                        else str(idx),
                        "close": round(float(row[close_col]), 2),
                    }
                )

            self.price_history = history_data
            self.price_history = []
        except Exception as e:
            logger.warning("Error fetching price history for %s: %s", self.selected_ticker, e)
            self.price_history = []

    def _compute_quality_check(self):
        """Compute quality assessment from ticker info."""
        flags = []

        # Check dividend yield for margin strategy (target > 3%)
        div_yield = self.ticker_info.get("dividend_yield") or 0
        if div_yield < 0.03:
            flags.append("Dividend below 3% margin target")

        # Check profitability
        profit_margin = self.ticker_info.get("profit_margin") or 0
        if profit_margin < 0.1:
            flags.append("Low profit margin (<10%)")

        # Check debt
        debt_ratio = self.ticker_info.get("debt_to_equity") or 0
        if debt_ratio > 2:
            flags.append("High debt/equity ratio (>2)")

        # Check P/E
        pe = self.ticker_info.get("pe_ratio")
        if pe and pe > 50:
            flags.append("High P/E ratio (>50)")
        elif pe and pe < 0:
            flags.append("Negative P/E (unprofitable)")

        self.quality_check = {
            "industry": self.ticker_info.get("industry", "Unknown"),
            "pe_ratio": self.ticker_info.get("pe_ratio"),
            "profit_margin": profit_margin,
            "debt_to_equity": debt_ratio,
            "dividend_yield": div_yield,
            "flags": flags,
            "overall": "Pass" if len(flags) < 2 else "Review",
        }

    def _compute_aggregate_sentiment(self):
        """Compute aggregate sentiment across all news items."""
        if not self.recent_news:
            self.aggregate_sentiment = {}
            return

        counts = {"positive": 0, "negative": 0, "neutral": 0}
        total_score = 0.0

        for item in self.recent_news:
            label = item.sentiment_label
            if label in counts:
                counts[label] += 1
            total_score += item.sentiment_score

        total = len(self.recent_news)
        dominant = max(counts, key=counts.get) if total > 0 else "neutral"
        avg_confidence = total_score / total if total > 0 else 0.5

        self.aggregate_sentiment = {
            "dominant": dominant,
            "counts": counts,
            "average_confidence": round(avg_confidence, 2),
            "total": total,
        }

    async def _fetch_options_data(self):
        """Fetch and process options chain data for current ticker.

        Loads all expirations, selects profile-appropriate default,
        and processes interesting strikes with annotations.
        """
        from ...services import services
        from ...state.user_context import UserContextState
        from .profiles import get_profile

        if not self.selected_ticker:
            return

        try:
            self.options_loading = True
            self.options_error = ""

            # Get user profile for default selection
            user_ctx = await self.get_state(UserContextState)
            profile = get_profile(user_ctx.active_profile)

            # Fetch all expirations
            expirations = services.market_data.get_options_expirations(
                self.selected_ticker
            )

            if not expirations:
                self.options_expirations = []
                self.selected_expiration = ""
                self.options_calls = []
                self.options_puts = []
                self.options_atm_iv = 0.0
                self.options_days_to_expiry = 0
                self.options_error = "No options listed for this ticker."
                self.options_summary = "No options listed."
                return

            self.options_expirations = expirations

            # Select default expiration based on profile
            default_exp = self._get_default_expiration_for_profile(
                expirations, profile.typical_timeframe
            )
            self.selected_expiration = default_exp

            # Load options for the default expiration
            await self._load_options_for_expiration()

        except Exception as e:
            logger.error("Error fetching options for %s: %s", self.selected_ticker, e)
            self.options_expirations = []
            self.selected_expiration = ""
            self.options_calls = []
            self.options_puts = []
            self.options_atm_iv = 0.0
            self.options_days_to_expiry = 0
            self.options_error = f"Error fetching options: {str(e)}"
            self.options_summary = "Error fetching options data."
        finally:
            self.options_loading = False

    def _get_default_expiration_for_profile(
        self, expirations: list[str], profile_timeframe: str
    ) -> str:
        """Select the best default expiration based on user profile.

        - Conservative (2_weeks): First expiration in 7-21 day range
        - Aggressive (1_2_months): First expiration in 30-60 day range
        - Standard (varies): First available expiration

        Falls back to first expiration if no match in preferred range.
        """
        from datetime import datetime, timedelta

        if not expirations:
            return ""

        today = datetime.now().date()

        # Define target ranges based on profile
        if profile_timeframe == "2_weeks":
            min_days, max_days = 7, 21
        elif profile_timeframe == "1_2_months":
            min_days, max_days = 30, 60
        else:
            # Standard or default: just use first expiration
            return expirations[0]

        # Find first expiration in target range
        for exp_str in expirations:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_out = (exp_date - today).days

                if min_days <= days_out <= max_days:
                    return exp_str
            except ValueError:
                continue

        # No match in preferred range - fallback to first expiration
        return expirations[0]

    async def _load_options_for_expiration(self):
        """Load and filter options chain for selected expiration.

        Uses cached data if available and not expired (5 min TTL).
        """
        from ...services import services
        from datetime import datetime

        if not self.selected_expiration or not self.selected_ticker:
            return

        try:
            self.options_loading = True

            # Calculate days to expiry
            exp_date = datetime.strptime(self.selected_expiration, "%Y-%m-%d").date()
            today = datetime.now().date()
            self.options_days_to_expiry = (exp_date - today).days

            # Check LRU cache first (bounded memory, TTL-aware)
            cache_key = f"{self.selected_ticker}:{self.selected_expiration}"
            cached_chain = _options_cache.get(cache_key)

            if cached_chain is not None:
                # Use cached data (TTL already checked by LRUCache)
                chain = cached_chain
            else:
                # Fetch fresh data
                chain = services.market_data.get_options_chain(
                    self.selected_ticker, self.selected_expiration
                )
                # Cache it (LRUCache handles eviction automatically)
                _options_cache.set(cache_key, chain)

            calls_df = chain.get("calls")
            puts_df = chain.get("puts")

            if calls_df is None or calls_df.empty:
                self.options_calls = []
                self.options_puts = []
                self.options_atm_iv = 0.0
                self._build_structured_options_summary()
                return

            # Get reference prices for filtering
            current_price = self.ticker_info.get("current_price", 0)
            range_high = self.price_range.get("high", 0)
            range_low = self.price_range.get("low", 0)
            target_price = self.analyst_data.get("target_price", 0)

            # Get interesting strikes
            all_strikes = sorted(calls_df["strike"].unique().tolist())
            interesting = self._get_interesting_strikes(
                all_strikes, current_price, range_high, range_low, target_price
            )

            strike_info = {s["strike"]: s for s in interesting}
            interesting_strikes = list(strike_info.keys())

            # Filter and format calls
            self.options_calls = self._format_options_rows(
                calls_df, interesting_strikes, strike_info, "call"
            )

            # Filter and format puts
            self.options_puts = self._format_options_rows(
                puts_df, interesting_strikes, strike_info, "put"
            )

            # Calculate ATM IV (average of ATM call and put IV)
            atm_strike = next((s["strike"] for s in interesting if s["is_atm"]), None)
            if atm_strike:
                ivs = []
                atm_call = calls_df[calls_df["strike"] == atm_strike]
                atm_put = puts_df[puts_df["strike"] == atm_strike]
                if not atm_call.empty and "impliedVolatility" in atm_call.columns:
                    iv = atm_call.iloc[0]["impliedVolatility"]
                    if iv and iv > 0:
                        ivs.append(iv)
                if not atm_put.empty and "impliedVolatility" in atm_put.columns:
                    iv = atm_put.iloc[0]["impliedVolatility"]
                    if iv and iv > 0:
                        ivs.append(iv)
                self.options_atm_iv = sum(ivs) / len(ivs) if ivs else 0
            else:
                self.options_atm_iv = 0.0

            # Build structured summary for LLM
            self._build_structured_options_summary()

        except Exception as e:
            logger.error(
                "Error loading options chain for %s/%s: %s",
                self.selected_ticker,
                self.selected_expiration,
                e,
            )
            self.options_calls = []
            self.options_puts = []
            self.options_atm_iv = 0.0
            self.options_error = f"Error loading chain: {str(e)}"
        finally:
            self.options_loading = False

    def _get_interesting_strikes(
        self,
        strikes: list[float],
        current_price: float,
        range_high: float,
        range_low: float,
        target_price: float,
    ) -> list[dict]:
        """Filter to 'interesting' strikes with annotations.

        Returns list of dicts: {strike, annotation, is_atm}
        """
        if not strikes or not current_price:
            return []

        interesting = []
        seen_strikes = set()

        # Define bounds: +/- 10% of current price
        lower_bound = current_price * 0.90
        upper_bound = current_price * 1.10

        # Find ATM strike (closest to current price)
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))

        # Find round number interval
        round_interval = 5 if current_price < 100 else 10

        for strike in sorted(strikes):
            if strike < lower_bound or strike > upper_bound:
                continue

            if strike in seen_strikes:
                continue

            annotation = ""
            is_atm = False

            # Check if ATM
            if strike == atm_strike:
                annotation = "ATM"
                is_atm = True
            # Check if near range high (within 2%)
            elif range_high and abs(strike - range_high) / range_high < 0.02:
                annotation = "Range High"
            # Check if near range low (within 2%)
            elif range_low and abs(strike - range_low) / range_low < 0.02:
                annotation = "Range Low"
            # Check if near analyst target (within 2%)
            elif target_price and abs(strike - target_price) / target_price < 0.02:
                annotation = "Target"
            # Check if round number
            elif strike % round_interval == 0:
                annotation = "Round"
            else:
                # Skip non-interesting strikes
                continue

            seen_strikes.add(strike)
            interesting.append(
                {
                    "strike": strike,
                    "annotation": annotation,
                    "is_atm": is_atm,
                }
            )

        # Always include ATM even if already captured
        if atm_strike not in seen_strikes:
            interesting.append(
                {
                    "strike": atm_strike,
                    "annotation": "ATM",
                    "is_atm": True,
                }
            )

        # Sort by strike and limit to ~8 strikes
        interesting.sort(key=lambda x: x["strike"])
        return interesting[:8]

    def _format_options_rows(
        self,
        df,
        interesting_strikes: list[float],
        strike_info: dict,
        option_type: str,
    ) -> list[dict]:
        """Format options DataFrame rows for display."""
        rows = []

        if df is None or df.empty:
            return rows

        filtered = df[df["strike"].isin(interesting_strikes)]

        for _, row in filtered.iterrows():
            strike = row["strike"]
            info = strike_info.get(strike, {})
            iv_raw = float(row.get("impliedVolatility", 0) or 0)

            rows.append(
                {
                    "strike": float(strike),
                    "bid": float(row.get("bid", 0) or 0),
                    "ask": float(row.get("ask", 0) or 0),
                    "oi": int(row.get("openInterest", 0) or 0),
                    "iv": iv_raw,
                    "iv_pct": f"{iv_raw * 100:.0f}%",  # Pre-formatted for display
                    "annotation": info.get("annotation", ""),
                    "is_atm": info.get("is_atm", False),
                }
            )

        # Sort calls descending (high strikes first), puts ascending
        if option_type == "call":
            rows.sort(key=lambda x: x["strike"], reverse=True)
        else:
            rows.sort(key=lambda x: x["strike"])

        return rows

    def _build_structured_options_summary(self):
        """Build structured options summary for LLM context."""
        if not self.options_calls and not self.options_puts:
            self.options_summary = "No options data available."
            return

        lines = [
            f"Options for {self.selected_expiration} ({self.options_days_to_expiry} days):",
            "",
            "Calls (sell if owning, buy if bullish):",
        ]

        for c in self.options_calls[:4]:
            ann = f" ({c['annotation']})" if c["annotation"] else ""
            lines.append(
                f"  ${c['strike']:.0f}{ann}: ${c['bid']:.2f} bid, IV {c['iv'] * 100:.0f}%"
            )

        lines.append("")
        lines.append("Puts (sell if bullish, buy if bearish):")

        for p in self.options_puts[:4]:
            ann = f" ({p['annotation']})" if p["annotation"] else ""
            lines.append(
                f"  ${p['strike']:.0f}{ann}: ${p['bid']:.2f} bid, IV {p['iv'] * 100:.0f}%"
            )

        if self.options_atm_iv:
            lines.append("")
            lines.append(f"ATM IV: {self.options_atm_iv * 100:.0f}%")

        self.options_summary = "\n".join(lines)

    async def set_volatility_horizon(self, horizon: str):
        """Handler for volatility horizon dropdown change."""
        self.volatility_horizon = horizon
        await self._fetch_volatility_data()

    async def _fetch_volatility_data(self):
        """Fetch and compute volatility analysis data.

        Requires:
        - Ticker selected
        - Options data loaded (for ATM IV)
        - Price history available

        Uses 1 year of price history for GARCH accuracy.
        """
        from ...services import services

        if not self.selected_ticker:
            return

        # Need ATM IV from options
        if self.options_atm_iv <= 0:
            self.volatility_error = "ATM IV not available"
            self.volatility_available = False
            return

        # Check if volatility service is available
        if not services.volatility.health_check():
            self.volatility_error = "Volatility service disabled or unavailable"
            self.volatility_available = False
            return

        try:
            self.volatility_loading = True
            self.volatility_error = ""

            # Get current price
            current_price = self.ticker_info.get("current_price", 0)
            if not current_price:
                self.volatility_error = "Current price not available"
                self.volatility_available = False
                return

            # Fetch 1 year of price history for GARCH accuracy
            df = services.market_data.get_price_history(
                self.selected_ticker, period="1y", interval="1d"
            )

            if df.empty or len(df) < 60:  # Need at least 60 days
                self.volatility_error = "Insufficient price history for GARCH"
                self.volatility_available = False
                return

            # Calculate log returns (lazy import to reduce startup memory)
            import numpy as np

            # Case-insensitive column access
            col_map = {c.lower(): c for c in df.columns}
            close_col = col_map.get("close")

            if not close_col:
                self.volatility_error = "Close price column not found"
                self.volatility_available = False
                return

            close_prices = df[close_col]
            returns = np.log(close_prices / close_prices.shift(1)).dropna()

            # Get horizon from state (string to int)
            horizon = int(self.volatility_horizon)

            # Run volatility comparison
            result = services.volatility.compare_to_implied_vol(
                current_price=current_price,
                returns=returns,
                implied_vol=self.options_atm_iv,
                horizon=horizon,
                confidence=0.68,
            )

            # Check for error
            if isinstance(result, dict) and "error" in result:
                self.volatility_error = result["error"]
                self.volatility_available = False
                return

            # Store results
            self.volatility_garch_vol = result.garch_annualized_vol
            self.volatility_implied_vol = result.implied_vol
            self.volatility_iv_garch_ratio = result.iv_garch_ratio
            self.volatility_iv_garch_diff = result.iv_garch_diff
            self.volatility_range_low = result.expected_range_low
            self.volatility_range_high = result.expected_range_high
            self.volatility_available = True

        except Exception as e:
            self.volatility_error = f"Error computing volatility: {str(e)}"
            self.volatility_available = False
        finally:
            self.volatility_loading = False

    def clear_research(self):
        """Clear all research data."""
        self.ticker_input = ""
        self.selected_ticker = ""
        self.ticker_info = {}
        self.quality_check = {}
        self.analyst_data = {}
        self.price_range = {}
        self.recent_news = []
        self.aggregate_sentiment = {}
        self.price_history = []
        self.selected_tab = "overview"
        self.error_message = ""
        # Clear options data
        self.options_expirations = []
        self.selected_expiration = ""
        self.options_calls = []
        self.options_puts = []
        self.options_atm_iv = 0.0
        self.options_days_to_expiry = 0
        self.options_error = ""
        self.options_summary = ""
        # Clear volatility data
        self.volatility_garch_vol = 0.0
        self.volatility_implied_vol = 0.0
        self.volatility_iv_garch_ratio = 0.0
        self.volatility_iv_garch_diff = 0.0
        self.volatility_range_low = 0.0
        self.volatility_range_high = 0.0
        self.volatility_horizon = "21"
        self.volatility_available = False
        self.volatility_error = ""
        self.volatility_loading = False
