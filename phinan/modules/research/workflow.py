"""Research workflow orchestration, packaged as a Reflex state mixin.

ResearchWorkflowMixin holds the async event handlers that drive a research run:
fetching market data, loading the options and volatility child states, computing
sentiment/quality, and generating the LLM synthesis. It is mixed into
ResearchState (see state.py), so ``self`` resolves to the full composed state at
runtime - including the core data vars and the _compute_* helpers defined there.
"""

import logging

import reflex as rx

from .research_models import NewsItem

logger = logging.getLogger(__name__)


class ResearchWorkflowMixin(rx.State, mixin=True):
    """Async orchestration event handlers for the Research module."""

    async def handle_search_key(self, key: str):
        """Handle key press in search input - trigger search on Enter."""
        if key == "Enter":
            async for _ in self.research_ticker():
                yield  # Yield each step to update UI

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

            from .options_state import OptionsState
            from .volatility_state import VolatilityState

            options_state = await self.get_state(OptionsState)
            volatility_state = await self.get_state(VolatilityState)

            # Options load first because volatility and synthesis consume its snapshot.
            await options_state._fetch_options_data()

            async with asyncio.TaskGroup() as tg:
                tg.create_task(
                    volatility_state._fetch_volatility_data_safe(
                        options_state.options_atm_iv
                    )
                )
                tg.create_task(self._fetch_price_history())
            yield

            self.loading_stage = "Generating AI Synthesis..."
            yield

            await self._apply_profile_insights()
            await self._generate_synthesis(
                options_summary=options_state.options_summary,
                options_expiration=options_state.selected_expiration,
            )
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

    async def _generate_synthesis(
        self,
        options_summary: str = "",
        options_expiration: str = "",
        force_refresh: bool = False,
    ):
        """Generate LLM synthesis of the research data.

        Args:
            options_summary: Structured options facts from OptionsState.
            options_expiration: Expiration selected in OptionsState.
            force_refresh: If True, bypass cache and regenerate synthesis
        """
        from ...services import services
        from ...services.synthesis import ResearchContext
        from ...state.user_context import UserContextState
        from .profiles import get_profile
        from datetime import datetime

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
            analysis_date = datetime.now().date().isoformat()
            news_context_lines = []
            for item in self.recent_news[:8]:
                publisher = item.publisher or "Unknown publisher"
                published = item.published or "Unknown date"
                news_context_lines.append(
                    f"- {published} | {publisher} | {item.title}"
                )
            news_context = "\n".join(news_context_lines)
            data_freshness = (
                f"Research data was assembled by the app on {analysis_date}. "
                "Ticker, range, analyst, news, and options facts are only current "
                "to the fetched app data shown here."
            )

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
                timeframe=user_ctx.typical_timeframe,
                default_range=user_ctx.default_range_period,
                portfolio_position=portfolio_position,
                options_summary=options_summary,
                options_expiration=options_expiration,
                analysis_date=analysis_date,
                data_freshness=data_freshness,
                news_context=news_context,
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
        """Manually refresh the AI synthesis using the current options snapshot."""
        from .options_state import OptionsState

        if not self.selected_ticker:
            return
        options_state = await self.get_state(OptionsState)
        await self._generate_synthesis(
            options_summary=options_state.options_summary,
            options_expiration=options_state.selected_expiration,
            force_refresh=True,
        )

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
        except Exception as e:
            logger.warning("Error fetching price history for %s: %s", self.selected_ticker, e)
            self.price_history = []
