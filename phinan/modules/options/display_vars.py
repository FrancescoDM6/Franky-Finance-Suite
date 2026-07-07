"""Computed display vars for the Options module, as Reflex state mixins."""

from typing import Any

import reflex as rx

from ..research.ticker_index import ticker_index


def _money(value: Any, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    sign = "+" if signed and value >= 0 else ("-" if signed and value < 0 else "")
    return f"{sign}${abs(value):,.2f}" if signed else f"${value:,.2f}"


def _pct(value: Any, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


class ChainVarsMixin(rx.State, mixin=True):
    """Chain viewer helpers."""

    @rx.var
    def has_chain_data(self) -> bool:
        return len(self.chain_calls) > 0 or len(self.chain_puts) > 0

    @rx.var
    def chain_spot_label(self) -> str:
        return f"${self.chain_spot:,.2f}" if self.chain_spot else ""

    @rx.var
    def chain_expiry_label(self) -> str:
        if not self.chain_expiration:
            return "Expiration"
        return f"{self.chain_expiration} ({self.chain_days_to_expiry}d)"

    @rx.var
    def ticker_suggestions(self) -> list[str]:
        if not self.form_chain_ticker:
            return []
        return ticker_index.search(self.form_chain_ticker, limit=8)


class PreviewVarsMixin(rx.State, mixin=True):
    """Strategy preview formatting."""

    @rx.var
    def has_preview(self) -> bool:
        return bool(self.preview)

    @rx.var
    def fmt_entry(self) -> str:
        amount = self.preview.get("entry_amount")
        if amount is None:
            return "N/A"
        kind = "Debit" if self.preview.get("is_debit") else "Credit"
        return f"{kind} {_money(amount)}"

    @rx.var
    def fmt_break_even(self) -> str:
        be = self.preview.get("break_even")
        return f"${be:,.2f}" if be is not None else "N/A"

    @rx.var
    def fmt_max_profit(self) -> str:
        if self.preview.get("unlimited_profit"):
            return "Unlimited"
        return _money(self.preview.get("max_profit"))

    @rx.var
    def fmt_max_loss(self) -> str:
        if self.preview.get("unlimited_loss"):
            return "Unlimited"
        return _money(self.preview.get("max_loss"))

    @rx.var
    def fmt_pop(self) -> str:
        return _pct(self.preview.get("pop"))

    @rx.var
    def has_greeks(self) -> bool:
        return bool(self.preview.get("greeks"))

    @rx.var
    def greek_rows(self) -> list[dict]:
        greeks = self.preview.get("greeks") or {}
        if not greeks:
            return []
        return [
            {"label": "Delta", "value": f"{greeks.get('delta', 0):+.3f}"},
            {"label": "Gamma", "value": f"{greeks.get('gamma', 0):+.4f}"},
            {"label": "Theta/day", "value": f"{greeks.get('theta', 0):+.3f}"},
            {"label": "Vega/pt", "value": f"{greeks.get('vega', 0):+.3f}"},
        ]

    @rx.var
    def payoff_data(self) -> list[dict]:
        return self.preview.get("payoff") or []

    @rx.var
    def is_editing(self) -> bool:
        return self.editing_trade_id > 0


class TradesVarsMixin(rx.State, mixin=True):
    """Trade tables helpers."""

    @rx.var
    def has_open_trades(self) -> bool:
        return len(self.open_trades) > 0

    @rx.var
    def has_closed_trades(self) -> bool:
        return len(self.closed_trades) > 0


class PerformanceVarsMixin(rx.State, mixin=True):
    """Performance dashboard formatting."""

    @rx.var
    def has_performance(self) -> bool:
        return (self.performance.get("trade_count") or 0) > 0

    @rx.var
    def fmt_win_rate(self) -> str:
        return _pct(self.performance.get("win_rate"))

    @rx.var
    def fmt_expectancy(self) -> str:
        return _money(self.performance.get("expectancy"), signed=True) + "/trade"

    @rx.var
    def fmt_total_pnl(self) -> str:
        return _money(self.performance.get("total_pnl"), signed=True)

    @rx.var
    def total_pnl_color(self) -> str:
        total = self.performance.get("total_pnl") or 0
        return "var(--green-11)" if total >= 0 else "var(--red-11)"

    @rx.var
    def fmt_avg_win(self) -> str:
        return _money(self.performance.get("avg_win"))

    @rx.var
    def fmt_avg_loss(self) -> str:
        return _money(self.performance.get("avg_loss"))

    @rx.var
    def fmt_avg_holding(self) -> str:
        days = self.performance.get("avg_holding_days")
        return f"{days:.1f} days" if days is not None else "N/A"

    @rx.var
    def fmt_record(self) -> str:
        wins = self.performance.get("win_count") or 0
        losses = self.performance.get("loss_count") or 0
        return f"{wins}W - {losses}L"

    @rx.var
    def by_strategy_rows(self) -> list[dict]:
        return self._format_breakdown(self.performance.get("by_strategy") or [])

    @rx.var
    def by_underlying_rows(self) -> list[dict]:
        return self._format_breakdown(self.performance.get("by_underlying") or [])

    def _format_breakdown(self, rows: list) -> list[dict]:
        formatted = []
        for row in rows:
            total = row.get("total_pnl") or 0
            formatted.append(
                {
                    "label": row.get("label") or row.get("key", ""),
                    "count": str(row.get("count", 0)),
                    "win_rate": _pct(row.get("win_rate")),
                    "total_pnl": _money(total, signed=True),
                    "pnl_color": "var(--green-11)" if total >= 0 else "var(--red-11)",
                }
            )
        return formatted

    @rx.var
    def can_analyze_patterns(self) -> bool:
        """Gate the LLM card until there is enough history to analyze."""
        return (self.performance.get("trade_count") or 0) >= 5
