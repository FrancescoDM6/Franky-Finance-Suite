"""Dashboard state and daily brief workflow."""

import logging
from datetime import datetime

import reflex as rx

from ...core.async_utils import run_sync
from ...state.user_context import UserContextState
from ..portfolio.state import PortfolioState
from .prompts import build_daily_brief_prompt

logger = logging.getLogger(__name__)


class DailyBriefState(rx.State):
    """State for the daily brief component."""

    brief_content: str = ""
    brief_loading: bool = False
    brief_error: str = ""
    brief_generated_at: str = ""
    _brief_date: str = ""
    loading_status: str = "Generating your brief..."
    news_alerts: list[dict] = []

    @rx.var
    def safe_brief_content(self) -> str:
        """Escape dollar signs to prevent LaTeX math mode."""
        return self.brief_content.replace("$", "\\$")

    async def generate_brief(self, force: bool = False):
        """Generate or retrieve today's daily brief."""
        from ...services import services
        from ..research.profiles import get_profile

        today = datetime.now().strftime("%Y-%m-%d")
        if not force and self._brief_date == today and self.brief_content:
            return

        if self.brief_loading:
            return

        self.brief_loading = True
        self.brief_error = ""
        self.loading_status = "Initializing..."
        yield

        try:
            user_ctx = await self.get_state(UserContextState)
            portfolio = await self.get_state(PortfolioState)

            profile = get_profile(user_ctx.active_profile)
            profile_name = profile.name
            profile_key = user_ctx.active_profile

            self.loading_status = "Fetching portfolio data..."
            yield
            position_lines = []
            for position in portfolio.positions[:5]:
                sign = "+" if position.gain_loss_percent >= 0 else ""
                position_lines.append(
                    f"- {position.ticker_symbol}: ${position.current_value:,.2f} "
                    f"({sign}{position.gain_loss_percent:.1f}%)"
                )
            position_summary = "\n".join(position_lines) if position_lines else ""

            movers_lines = []
            for gainer in portfolio.top_gainers[:2]:
                movers_lines.append(
                    f"- {gainer['symbol']}: +{gainer['change_pct']:.1f}% (gainer)"
                )
            for loser in portfolio.top_losers[:2]:
                if loser["change_pct"] < 0:
                    movers_lines.append(
                        f"- {loser['symbol']}: {loser['change_pct']:.1f}% (loser)"
                    )
            movers_summary = "\n".join(movers_lines) if movers_lines else ""

            self.loading_status = "Fetching watchlist data..."
            yield
            watchlist_lines = []
            for symbol in user_ctx.watchlist[:5]:
                try:
                    info = await services.market_data.get_ticker_info_async(symbol)
                    if info:
                        watchlist_lines.append(f"- {symbol}: ${info.current_price:.2f}")
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch watchlist info for %s: %s", symbol, exc
                    )
            watchlist_summary = "\n".join(watchlist_lines) if watchlist_lines else ""

            self.loading_status = "Fetching news for holdings..."
            yield
            news_lines = []
            self.news_alerts = []
            for ticker in portfolio.position_tickers[:5]:
                try:
                    news = await services.market_data.get_news_async(ticker, max_items=2)
                    for item in news:
                        published = (
                            item.published.isoformat()
                            if getattr(item, "published", None)
                            else "Unknown date"
                        )
                        publisher = item.publisher or "Unknown publisher"
                        news_lines.append(
                            f"- [{ticker}] {published} | {publisher} | {item.title}"
                        )
                        self.news_alerts.append(
                            {
                                "ticker": ticker,
                                "title": item.title,
                                "publisher": item.publisher,
                                "link": item.link,
                            }
                        )
                except Exception as exc:
                    logger.warning("Failed to fetch news for %s: %s", ticker, exc)
            news_summary = "\n".join(news_lines[:6]) if news_lines else ""

            if not await run_sync(services.llm.health_check):
                logger.info("LLM unavailable, using fallback brief.")
                self.brief_content = self._build_fallback_brief(
                    profile_name, portfolio, user_ctx
                )
                self.brief_generated_at = datetime.now().strftime("%I:%M %p")
                self._brief_date = today
                return

            prompt = build_daily_brief_prompt(
                profile_name=profile_name,
                profile_key=profile_key,
                total_value=portfolio.total_value,
                total_pl_pct=portfolio.total_gain_loss_percent,
                position_count=len(portfolio.positions),
                position_summary=position_summary,
                movers_summary=movers_summary,
                watchlist_summary=watchlist_summary,
                news_summary=news_summary,
                analysis_date=today,
                data_freshness=(
                    f"Brief data was assembled by the app on {today}. "
                    "Prices, movers, and news are only current to the fetched app data shown here."
                ),
                timeframe=user_ctx.typical_timeframe,
                avoid_list=", ".join(user_ctx.avoid_list),
            )

            self.loading_status = "Generating summary with AI..."
            yield
            self.brief_content = await services.llm.complete_async(prompt)
            self.brief_generated_at = datetime.now().strftime("%I:%M %p")
            self._brief_date = today
        except Exception as exc:
            self.brief_error = f"Error generating brief: {str(exc)}"
            logger.error("Daily brief error: %s", exc, exc_info=True)
        finally:
            self.brief_loading = False

    def _build_fallback_brief(self, profile_name: str, portfolio, user_ctx) -> str:
        """Build a basic brief when the LLM is unavailable."""
        lines = [f"## Good morning, {profile_name}!", ""]

        if portfolio.has_positions:
            sign = "+" if portfolio.total_gain_loss_percent >= 0 else ""
            lines.extend(
                [
                    "### Portfolio Snapshot",
                    f"Your portfolio is at **${portfolio.total_value:,.2f}** "
                    f"({sign}{portfolio.total_gain_loss_percent:.1f}% overall).",
                    "",
                ]
            )

        if user_ctx.watchlist:
            lines.extend(
                [
                    "### Watchlist",
                    f"Tracking {len(user_ctx.watchlist)} stocks.",
                    "",
                ]
            )

        lines.append("*LLM unavailable - showing basic summary.*")
        return "\n".join(lines)

    async def force_regenerate_brief(self):
        """Regenerate the brief without consulting the daily cache."""
        async for _ in self.generate_brief(force=True):
            yield
