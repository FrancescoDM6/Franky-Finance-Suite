"""Research module state.

Manages ticker research data, quality checks, and analysis.
"""

import reflex as rx
from typing import Any, Optional


class NewsItem(rx.Base):
    """News item model for frontend. Uses rx.Base for proper foreach access."""
    title: str = ""
    publisher: str = ""
    published: str = ""
    link: str = ""  # URL to article
    sentiment_label: str = "neutral"  # "positive", "negative", "neutral"
    sentiment_score: float = 0.5  # 0-1 confidence


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

    # Loading states
    is_loading: bool = False
    loading_stage: str = ""
    error_message: str = ""

    # Results (dicts for Reflex serialization)
    ticker_info: dict[str, Any] = {}
    quality_check: dict[str, Any] = {}
    analyst_data: dict[str, Any] = {}
    price_range: dict[str, Any] = {}

    recent_news: list[NewsItem] = []
    
    # Profile-aware insights
    profile_insights: list[str] = []
    
    # LLM synthesis
    llm_synthesis: str = ""
    is_generating_synthesis: bool = False
    
    # New: Tab and Chart state
    selected_tab: str = "overview"
    chart_period: str = "3mo"
    price_history: list[dict[str, Any]] = []  # [{date, open, high, low, close, volume}, ...]

    # Ticker Validation Data
    tickers: list[dict] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_tickers()

    def _load_tickers(self):
        """Load tickers from JSON file."""
        import json
        import os
        
        try:
            # Construct path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(current_dir, "data", "tickers.json")
            
            with open(data_path, "r") as f:
                self.tickers = json.load(f)
        except Exception as e:
            print(f"Error loading tickers: {e}")
            self.tickers = []

    @rx.var
    def ticker_options(self) -> list[str]:
        """Filter tickers based on input."""
        if not self.ticker_input:
            return []
            
        search_term = self.ticker_input.upper()
        options = []
        
        # Simple fuzzy search
        count = 0
        for t in self.tickers:
            if search_term in t["symbol"] or search_term in t["name"].upper():
                options.append(f"{t['symbol']} - {t['name']}")
                count += 1
                if count >= 10:  # Limit to 10 suggestions
                    break
                    
        return options

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

    async def handle_search_key(self, key: str):
        """Handle key press in search input - trigger search on Enter."""
        if key == "Enter":
            async for _ in self.research_ticker():
                pass

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

    def set_ticker_input(self, value: str):
        """Update ticker input."""
        self.ticker_input = value.upper()

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

        self.is_loading = True
        self.loading_stage = "Fetching Market Data..."
        self.error_message = ""
        
        # Yield immediately to show loading state
        yield
        
        # Store the input but don't update selected_ticker yet
        raw_input = self.ticker_input.strip().upper()
        
        # Handle "SYMBOL - Name" format from autocomplete
        if " - " in raw_input:
            ticker_to_lookup = raw_input.split(" - ")[0]
        else:
            ticker_to_lookup = raw_input

        try:
            from ...services import services

            # Fetch ticker info first to validate
            info = services.market_data.get_ticker_info(ticker_to_lookup)

            if not info:
                self.error_message = f"Could not find ticker: {ticker_to_lookup}. Try using the stock symbol (e.g., NFLX for Netflix)."
                self.is_loading = False
                self.loading_stage = ""
                return
            
            # Only update selected_ticker after successful validation
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
            }

            self.loading_stage = "Analyzing Price Action..."
            # Yield to update UI
            yield 

            # Fetch price range
            range_data = services.market_data.get_price_range(
                self.selected_ticker, self.range_period
            )
            if range_data:
                self.price_range = {
                    "period": range_data.period,
                    "high": range_data.high,
                    "low": range_data.low,
                    "current": range_data.current,
                    "percent_of_range": range_data.percent_of_range,
                }
            
            self.loading_stage = "Fetching News & Sentiment..."
            yield

            # Fetch news
            news = services.market_data.get_news(self.selected_ticker)
            news_items = news[:5]
            
            # Score sentiment if service available
            sentiment_scores = []
            if services.sentiment.health_check():
                self.loading_stage = "Loading Sentiment Model (first time may take a moment)..."
                yield
                titles = [item.title for item in news_items]
                sentiment_scores = services.sentiment.score_batch(titles)
            
            # Build news items with sentiment
            self.recent_news = []
            for i, item in enumerate(news_items):
                sentiment = sentiment_scores[i] if i < len(sentiment_scores) else {}
                self.recent_news.append(NewsItem(
                    title=item.title,
                    publisher=item.publisher,
                    published=item.published.isoformat(),
                    link=item.link,
                    sentiment_label=sentiment.get("label", "neutral"),
                    sentiment_score=sentiment.get("score", 0.5),
                ))
            
            self.loading_stage = "Calculating Quality Metrics..."
            yield

            # Compute quality check
            self._compute_quality_check()
            
            # Fetch price history for charts
            await self._fetch_price_history()
            
            self.loading_stage = "Generating AI Synthesis..."
            yield

            # Apply profile-aware insights
            await self._apply_profile_insights()
            
            # Generate LLM synthesis (non-blocking, happens in background)
            await self._generate_synthesis()

        except Exception as e:
            self.error_message = f"Error: {str(e)}"
        finally:
            self.is_loading = False
            self.loading_stage = ""

    async def _generate_synthesis(self):
        """Generate LLM synthesis of the research data."""
        from ...services import services
        from ...state.user_context import UserContextState
        from .profiles import get_profile
        from .prompts import build_analysis_prompt
        
        # Check if LLM is available
        if not services.llm.health_check():
            self.llm_synthesis = ""
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
                print(f"Could not fetch portfolio context: {e}")
            
            # Determine aggregate news sentiment
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for item in self.recent_news:
                sentiment_counts[item.sentiment_label] = sentiment_counts.get(item.sentiment_label, 0) + 1
            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            
            # Build prompt
            prompt = build_analysis_prompt(
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
            )
            
            # Call LLM
            response = services.llm.complete(prompt)
            self.llm_synthesis = response
            
        except Exception as e:
            print(f"Error generating LLM synthesis: {e}")
            self.llm_synthesis = ""
        finally:
            self.is_generating_synthesis = False

    async def _apply_profile_insights(self):
        """Generate profile-specific insights based on active user profile."""
        from ...state.user_context import UserContextState
        from .profiles import get_papi_insights, get_tio_insights, get_franky_insights
        
        try:
            # Get user context state to find active profile
            user_ctx = await self.get_state(UserContextState)
            profile = user_ctx.active_profile.lower()
            
            # Convert NewsItem objects to dicts for insight functions
            news_dicts = [{"title": n.title, "publisher": n.publisher} for n in self.recent_news]
            
            if profile == "papi":
                self.profile_insights = get_papi_insights(
                    self.ticker_info, self.price_range, self.analyst_data
                )
            elif profile == "tio":
                self.profile_insights = get_tio_insights(
                    self.ticker_info, self.price_range, news_dicts, self.analyst_data
                )
            else:
                # Franky or default
                self.profile_insights = get_franky_insights(
                    self.ticker_info, self.price_range, news_dicts, self.analyst_data
                )
        except Exception as e:
            print(f"Error generating profile insights: {e}")
            self.profile_insights = []


    async def _fetch_price_history(self):
        """Fetch price history for charts."""
        if not self.selected_ticker:
            return
        
        try:
            from ...services import services
            
            df = services.market_data.get_price_history(
                self.selected_ticker, 
                period=self.chart_period,
                interval="1d"
            )
            
            if df.empty:
                self.price_history = []
                return
            
            # Convert DataFrame to list of dicts for Reflex
            history_data = []
            for idx, row in df.iterrows():
                history_data.append({
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]) if "Volume" in row else 0,
                })
            
            self.price_history = history_data
        except Exception as e:
            print(f"Error fetching price history: {e}")
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

    def clear_research(self):
        """Clear all research data."""
        self.ticker_input = ""
        self.selected_ticker = ""
        self.ticker_info = {}
        self.quality_check = {}
        self.analyst_data = {}
        self.price_range = {}
        self.recent_news = []
        self.price_history = []
        self.selected_tab = "overview"
        self.error_message = ""
