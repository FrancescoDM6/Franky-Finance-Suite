"""Home page / Dashboard with Phin Daily Brief."""

import logging
from datetime import datetime

import reflex as rx

from ..components.layout import main_layout
from ..components.ui import content_card, synthesis_card
from ..core.async_utils import run_sync
from ..state.user_context import UserContextState
from ..modules.portfolio.state import PortfolioState
from .prompts import build_daily_brief_prompt

logger = logging.getLogger(__name__)


class DailyBriefState(rx.State):
    """State for the daily brief component."""

    brief_content: str = ""
    brief_loading: bool = False
    brief_error: str = ""
    brief_generated_at: str = ""
    _brief_date: str = ""  # Track which date brief was generated for
    loading_status: str = "Generating your brief..."  # For Thinking UI pattern

    # News alerts for holdings
    news_alerts: list[dict] = []

    @rx.var
    def safe_brief_content(self) -> str:
        """Escape $ signs to prevent LaTeX math mode."""
        return self.brief_content.replace("$", "\\$")

    async def generate_brief(self, force: bool = False):
        """Generate the daily brief using LLM.

        Only regenerates if not already generated today (unless forced).
        """
        from ..services import services
        from ..modules.research.profiles import get_profile

        # Check if already generated today (skip if forced)
        today = datetime.now().strftime("%Y-%m-%d")
        if not force and self._brief_date == today and self.brief_content:
            return  # Already have today's brief

        if self.brief_loading:
            return

        self.brief_loading = True
        self.brief_error = ""
        self.loading_status = "Initializing..."
        yield

        try:
            # Get user context
            user_ctx = await self.get_state(UserContextState)
            portfolio = await self.get_state(PortfolioState)

            profile = get_profile(user_ctx.active_profile)
            profile_name = profile.name
            profile_key = user_ctx.active_profile

            # Build position summary
            self.loading_status = "Fetching portfolio data..."
            yield
            position_lines = []
            for pos in portfolio.positions[:5]:
                sign = "+" if pos.gain_loss_percent >= 0 else ""
                position_lines.append(
                    f"- {pos.ticker_symbol}: ${pos.current_value:,.2f} ({sign}{pos.gain_loss_percent:.1f}%)"
                )
            position_summary = "\n".join(position_lines) if position_lines else ""

            # Build movers summary
            movers_lines = []
            if portfolio.top_gainers:
                for g in portfolio.top_gainers[:2]:
                    movers_lines.append(f"- {g['symbol']}: +{g['change_pct']:.1f}% (gainer)")
            if portfolio.top_losers:
                for l in portfolio.top_losers[:2]:
                    if l["change_pct"] < 0:
                        movers_lines.append(f"- {l['symbol']}: {l['change_pct']:.1f}% (loser)")
            movers_summary = "\n".join(movers_lines) if movers_lines else ""

            # Build watchlist summary
            self.loading_status = "Fetching watchlist data..."
            yield
            watchlist_lines = []
            for symbol in user_ctx.watchlist[:5]:
                try:
                    info = await services.market_data.get_ticker_info_async(symbol)
                    if info:
                        watchlist_lines.append(f"- {symbol}: ${info.current_price:.2f}")
                except Exception as e:
                    logger.warning("Failed to fetch watchlist info for %s: %s", symbol, e)
                    continue
            watchlist_summary = "\n".join(watchlist_lines) if watchlist_lines else ""

            # Fetch news for portfolio holdings
            self.loading_status = "Fetching news for holdings..."
            yield
            news_lines = []
            self.news_alerts = []
            for ticker in portfolio.position_tickers[:5]:
                try:
                    news = await services.market_data.get_news_async(ticker, max_items=2)
                    for item in news:
                        news_lines.append(f"- [{ticker}] {item.title}")
                        self.news_alerts.append({
                            "ticker": ticker,
                            "title": item.title,
                            "publisher": item.publisher,
                            "link": item.link,
                        })
                except Exception as e:
                    logger.warning("Failed to fetch news for %s: %s", ticker, e)
                    continue
            news_summary = "\n".join(news_lines[:6]) if news_lines else ""

            # Check if LLM is available
            if not await run_sync(services.llm.health_check):
                logger.info("LLM unavailable, using fallback brief.")
                self.brief_content = self._build_fallback_brief(
                    profile_name, portfolio, user_ctx
                )
                self.brief_generated_at = datetime.now().strftime("%I:%M %p")
                self._brief_date = today  # Prevent refetching on every page load
                return

            # Build prompt
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
            )

            # Call LLM
            self.loading_status = "Generating summary with AI..."
            yield
            response = await services.llm.complete_async(prompt)
            self.brief_content = response
            self.brief_generated_at = datetime.now().strftime("%I:%M %p")
            self._brief_date = today  # Mark brief as generated for today

        except Exception as e:
            self.brief_error = f"Error generating brief: {str(e)}"
            logger.error("Daily brief error: %s", e, exc_info=True)
        finally:
            self.brief_loading = False

    def _build_fallback_brief(self, profile_name: str, portfolio, user_ctx) -> str:
        """Build a simple brief when LLM is unavailable."""
        lines = [f"## Good morning, {profile_name}!", ""]

        if portfolio.has_positions:
            sign = "+" if portfolio.total_gain_loss_percent >= 0 else ""
            lines.append("### Portfolio Snapshot")
            lines.append(
                f"Your portfolio is at **${portfolio.total_value:,.2f}** "
                f"({sign}{portfolio.total_gain_loss_percent:.1f}% overall)."
            )
            lines.append("")

        if user_ctx.watchlist:
            lines.append("### Watchlist")
            lines.append(f"Tracking {len(user_ctx.watchlist)} stocks.")
            lines.append("")

        lines.append("*LLM unavailable - showing basic summary.*")
        return "\n".join(lines)

    async def force_regenerate_brief(self):
        """Force regenerate the brief (for refresh button)."""
        async for _ in self.generate_brief(force=True):
            yield


def stat_card(title: str, value: rx.Var | str, subtitle: str = "", color_scheme: str = "gray") -> rx.Component:
    """Statistics card component."""
    return content_card(
        rx.vstack(
            rx.text(title, size="1", color_scheme="gray"),
            rx.heading(value, size="5"),
            rx.cond(
                subtitle != "",
                rx.text(subtitle, size="1", color_scheme=color_scheme),
                rx.fragment(),
            ),
            spacing="1",
            align="start",
        ),
        width="100%",
    )


def daily_brief_card() -> rx.Component:
    """Phin's Daily Brief card."""
    return synthesis_card(
        rx.vstack(
            # Header with refresh button
            rx.hstack(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--purple-9)"),
                    rx.heading("Phin's Daily Brief", size="4"),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.cond(
                        DailyBriefState.brief_generated_at != "",
                        rx.text(DailyBriefState.brief_generated_at, size="1", color_scheme="gray"),
                        rx.fragment(),
                    ),
                    rx.button(
                        rx.icon("refresh-cw", size=14),
                        on_click=DailyBriefState.force_regenerate_brief,
                        variant="ghost",
                        size="1",
                        loading=DailyBriefState.brief_loading,
                    ),
                    spacing="2",
                    align="center",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            # Brief content
            rx.cond(
                DailyBriefState.brief_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="2"),
                        rx.text(DailyBriefState.loading_status, size="1", color_scheme="gray"),
                        spacing="2",
                        align="center",
                    ),
                    padding="6",
                ),
                rx.cond(
                    DailyBriefState.brief_error != "",
                    rx.callout(
                        DailyBriefState.brief_error,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.cond(
                        DailyBriefState.brief_content != "",
                        rx.markdown(
                            DailyBriefState.safe_brief_content,
                            component_map={
                                "h2": lambda text: rx.heading(text, size="4", margin_top="0.5em", margin_bottom="0.25em"),
                                "h3": lambda text: rx.heading(text, size="3", margin_top="0.5em", margin_bottom="0.25em"),
                                "p": lambda text: rx.text(text, size="2", margin_bottom="0.5em"),
                                "li": lambda text: rx.text(text, size="2", display="list-item", margin_left="1em"),
                            },
                        ),
                        rx.center(
                            rx.vstack(
                                rx.icon("sun", size=32, color="var(--amber-9)"),
                                rx.text("Click refresh to generate today's brief", size="2", color_scheme="gray"),
                                spacing="2",
                                align="center",
                            ),
                            padding="6",
                        ),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def news_alerts_card() -> rx.Component:
    """Compact news alerts for holdings."""
    return rx.cond(
        DailyBriefState.news_alerts.length() > 0,
        content_card(
            rx.vstack(
                rx.hstack(
                    rx.icon("bell", size=16, color="var(--amber-9)"),
                    rx.heading("News Alerts", size="4"),
                    rx.spacer(),
                    rx.badge(
                        DailyBriefState.news_alerts.length(),
                        variant="soft",
                        size="1",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.divider(),
                rx.foreach(
                    DailyBriefState.news_alerts[:5],
                    lambda item: rx.hstack(
                        rx.badge(item["ticker"], size="1", variant="soft"),
                        rx.link(
                            rx.text(item["title"], size="1", style={"text_overflow": "ellipsis", "overflow": "hidden", "white_space": "nowrap"}),
                            href=item["link"],
                            is_external=True,
                            style={"flex": "1", "min_width": "0"},
                        ),
                        spacing="2",
                        width="100%",
                        align="center",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


def portfolio_mini_summary() -> rx.Component:
    """Compact portfolio summary card."""
    return content_card(
        rx.vstack(
            rx.hstack(
                rx.icon("briefcase", size=16),
                rx.heading("Portfolio", size="4"),
                rx.spacer(),
                rx.link(
                    rx.text("View all", size="1"),
                    href="/portfolio",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            rx.cond(
                PortfolioState.has_positions,
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.text("Total Value", size="1", color_scheme="gray"),
                            rx.text(
                                PortfolioState.fmt_total_value,
                                size="4",
                                weight="bold",
                            ),
                            spacing="0",
                            align="start",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.text("P/L", size="1", color_scheme="gray"),
                            rx.text(
                                PortfolioState.fmt_total_pl_pct,
                                size="3",
                                weight="bold",
                                color=rx.cond(
                                    PortfolioState.total_gain_loss_percent >= 0,
                                    "var(--green-11)",
                                    "var(--red-11)",
                                ),
                            ),
                            spacing="0",
                            align="end",
                        ),
                        width="100%",
                    ),
                    rx.text(
                        PortfolioState.positions.length(),
                        " positions",
                        size="1",
                        color_scheme="gray",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.center(
                    rx.text("No positions yet", size="2", color_scheme="gray"),
                    padding="4",
                ),
            ),
            spacing="2",
            width="100%",
        ),
        width="100%",
    )


def quick_add_position_dialog() -> rx.Component:
    """Dialog for adding position from home page."""
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=16),
                "Add Position",
                variant="soft",
                color_scheme="green",
                size="2",
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("Add Position"),
            rx.dialog.description("Add a new stock to your portfolio."),
            rx.vstack(
                rx.input(
                    placeholder="Ticker (e.g., AAPL)",
                    value=PortfolioState.form_ticker,
                    on_change=PortfolioState.set_form_ticker,
                    width="100%",
                ),
                rx.input(
                    placeholder="Quantity",
                    type="number",
                    value=PortfolioState.form_quantity,
                    on_change=PortfolioState.set_form_quantity,
                    width="100%",
                ),
                rx.input(
                    placeholder="Cost per share",
                    type="number",
                    value=PortfolioState.form_cost_basis,
                    on_change=PortfolioState.set_form_cost_basis,
                    width="100%",
                ),
                rx.cond(
                    PortfolioState.error_message != "",
                    rx.callout(
                        PortfolioState.error_message,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel", variant="soft", color_scheme="gray"),
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Add",
                            on_click=PortfolioState.add_position,
                            color_scheme="green",
                        ),
                    ),
                    spacing="2",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                padding_top="2",
            ),
            style={"max_width": "400px"},
        ),
    )


def quick_actions() -> rx.Component:
    """Enhanced quick actions section."""
    return content_card(
        rx.vstack(
            rx.hstack(
                rx.icon("zap", size=16),
                rx.heading("Quick Actions", size="4"),
                spacing="2",
                align="center",
            ),
            rx.divider(),
            rx.grid(
                # Primary actions
                rx.link(
                    rx.button(
                        rx.icon("search", size=16),
                        "Research",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/research",
                    width="100%",
                ),
                quick_add_position_dialog(),
                rx.link(
                    rx.button(
                        rx.icon("bar-chart-4", size=16),
                        "Options",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/options",
                    width="100%",
                ),
                rx.link(
                    rx.button(
                        rx.icon("file-text", size=16),
                        "Notes",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/notes",
                    width="100%",
                ),
                columns="2",
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def dashboard_content() -> rx.Component:
    """Home dashboard content."""
    return rx.vstack(
        # Header row
        rx.hstack(
            rx.vstack(
                rx.heading("Welcome back", size="6"),
                rx.badge(
                    UserContextState.profile_display_name,
                    variant="soft",
                    size="2",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.badge(
                rx.hstack(
                    rx.icon("activity", size=14),
                    rx.text("Markets Open", size="1"),
                    spacing="1",
                ),
                color_scheme="green",
                variant="soft",
            ),
            width="100%",
            align="center",
        ),
        rx.divider(),

        # Main grid: Brief (left) + Stats/Actions (right)
        rx.grid(
            # Left column: Daily Brief
            daily_brief_card(),

            # Right column: Portfolio + Actions
            rx.hstack(
                portfolio_mini_summary(),
                quick_actions(),
                spacing="4",
                width="100%",
            ),

            columns=rx.breakpoints({"0px": "1", "768px": "2"}),
            spacing="4",
            width="100%",
        ),

        # News alerts row
        news_alerts_card(),

        spacing="4",
        width="100%",
        align="start",
    )



@rx.page(
    route="/",
    title="Home | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions, DailyBriefState.generate_brief],
)
def index() -> rx.Component:
    """Home page."""
    return main_layout(dashboard_content())
