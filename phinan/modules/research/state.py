"""Research module state.

Manages ticker research data, quality checks, and analysis.
"""

import reflex as rx
from typing import Any, Optional


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
    error_message: str = ""

    # Results (dicts for Reflex serialization)
    ticker_info: dict[str, Any] = {}
    quality_check: dict[str, Any] = {}
    analyst_data: dict[str, Any] = {}
    price_range: dict[str, Any] = {}
    recent_news: list[dict[str, Any]] = []

    @rx.var
    def has_results(self) -> bool:
        """Whether we have loaded results."""
        return bool(self.selected_ticker and self.ticker_info)

    @rx.var
    def current_price(self) -> Optional[float]:
        """Current price from ticker info."""
        return self.ticker_info.get("current_price")

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
        self.error_message = ""
        self.selected_ticker = self.ticker_input.strip().upper()

        try:
            from ...services import services

            # Fetch ticker info
            info = services.market_data.get_ticker_info(self.selected_ticker)

            if not info:
                self.error_message = f"Could not find ticker: {self.selected_ticker}"
                self.is_loading = False
                return

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

            # Fetch news
            news = services.market_data.get_news(self.selected_ticker)
            self.recent_news = [
                {
                    "title": item.title,
                    "publisher": item.publisher,
                    "published": item.published.isoformat(),
                }
                for item in news[:5]
            ]

            # Compute quality check
            self._compute_quality_check()

        except Exception as e:
            self.error_message = f"Error: {str(e)}"
        finally:
            self.is_loading = False

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
        self.error_message = ""
