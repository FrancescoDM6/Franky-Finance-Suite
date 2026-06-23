"""Computed display vars for the Research module, grouped as state mixins.

Each mixin is a Reflex ``mixin=True`` state that contributes only computed vars.
The underlying data vars (ticker_info, analyst_data, price_range,
aggregate_sentiment, quality_check, llm_synthesis, ticker_input, price_history)
are declared on ResearchState; the computed vars below read them via ``self`` and
are resolved against the composed state at runtime. Splitting them out keeps
state.py focused on data and workflow.
"""

from typing import Optional

import reflex as rx

from .ticker_index import ticker_index


class CoreVarsMixin(rx.State, mixin=True):
    """General computed vars derived from core research data."""

    @rx.var
    def safe_llm_synthesis(self) -> str:
        """Escape $ signs to prevent LaTeX math mode in markdown."""
        # Replace $ with escaped version to prevent math rendering
        return self.llm_synthesis.replace("$", "\\$")

    @rx.var
    def ticker_options(self) -> list[str]:
        """Filter tickers based on input using pre-built index.

        Uses TickerIndex for O(1) average case instead of O(n) linear scan.
        """
        if not self.ticker_input:
            return []

        # Use the global pre-built index for fast search
        return ticker_index.search(self.ticker_input, limit=10)

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
    def has_chart_data(self) -> bool:
        """Whether we have chart data."""
        return len(self.price_history) > 0


class RangeVarsMixin(rx.State, mixin=True):
    """Computed vars for price-range presentation."""

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
    def is_near_range_high(self) -> bool:
        """True if current price is in upper 25% of range."""
        pct = self.price_range.get("percent_of_range", 0.5)
        return pct > 0.75 if pct is not None else False

    @rx.var
    def is_near_range_low(self) -> bool:
        """True if current price is in lower 25% of range."""
        pct = self.price_range.get("percent_of_range", 0.5)
        return pct < 0.25 if pct is not None else False


class QualityVarsMixin(rx.State, mixin=True):
    """Computed vars for the quality card and fundamentals formatting."""

    @rx.var
    def quality_overall(self) -> str:
        """Overall quality assessment."""
        return self.quality_check.get("overall", "N/A")

    @rx.var
    def quality_flags(self) -> list[str]:
        """Quality warning flags."""
        return self.quality_check.get("flags", [])

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


class AnalystVarsMixin(rx.State, mixin=True):
    """Computed vars for analyst recommendations and price targets."""

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


class SentimentVarsMixin(rx.State, mixin=True):
    """Computed vars for aggregate news sentiment."""

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
