"""Pure P/L and performance analytics for logged options trades.

No Reflex imports. Premiums and exit prices are per share; the 100x
contract multiplier is applied here when producing dollar amounts.
"""

import logging
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

CONTRACT_MULTIPLIER = 100

STRATEGY_LABELS = {
    "long_call": "Long Call",
    "long_put": "Long Put",
    "covered_call": "Covered Call",
    "cash_secured_put": "Cash-Secured Put",
}


def compute_realized_pnl(
    position_type: str, premium: float, exit_price: float, quantity: int
) -> float:
    """Realized dollar P/L for a closed single-leg trade.

    long:  (exit - premium) * 100 * quantity
    short: (premium - exit) * 100 * quantity
    Expired-worthless is a close with exit_price = 0 (a long loses the
    premium, a short keeps it).
    """
    per_share = (
        exit_price - premium if position_type == "long" else premium - exit_price
    )
    return round(per_share * CONTRACT_MULTIPLIER * quantity, 2)


def holding_days(opened_at: datetime, closed_at: datetime) -> int:
    """Calendar days a trade was held (never negative)."""
    return max(0, (closed_at - opened_at).days)


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def compute_performance(closed_trades: List[dict]) -> dict:
    """Aggregate performance metrics from closed/expired trades.

    Input rows need: realized_pnl, strategy, ticker_symbol, opened_at,
    closed_at. Returns a JSON-safe dict; empty input returns
    {"trade_count": 0} and the UI renders an empty state.

    Win/loss convention: pnl > 0 is a win; pnl == 0 counts as a loss
    (a scratch trade did not make money). avg_loss is reported as a
    positive magnitude. Expectancy = avg_win * win_rate - avg_loss *
    loss_rate (per-trade expected value).
    """
    trades = [t for t in closed_trades if t.get("realized_pnl") is not None]
    if not trades:
        return {"trade_count": 0}

    pnls = [float(t["realized_pnl"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    win_rate = len(wins) / len(pnls)
    loss_rate = 1.0 - win_rate
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    expectancy = avg_win * win_rate - avg_loss * loss_rate

    holding = []
    for t in trades:
        try:
            holding.append(
                holding_days(_parse_dt(t["opened_at"]), _parse_dt(t["closed_at"]))
            )
        except (KeyError, TypeError, ValueError):
            continue

    def _breakdown(key_field: str, label_map: dict | None = None) -> List[dict]:
        groups: dict = {}
        for t in trades:
            key = t.get(key_field) or "unknown"
            groups.setdefault(key, []).append(float(t["realized_pnl"]))
        rows = []
        for key, group in groups.items():
            group_wins = sum(1 for p in group if p > 0)
            rows.append(
                {
                    "key": key,
                    "label": (label_map or {}).get(key, key),
                    "count": len(group),
                    "win_rate": round(group_wins / len(group), 4),
                    "total_pnl": round(sum(group), 2),
                }
            )
        rows.sort(key=lambda r: r["total_pnl"], reverse=True)
        return rows

    return {
        "trade_count": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_holding_days": round(sum(holding) / len(holding), 1) if holding else 0.0,
        "by_strategy": _breakdown("strategy", STRATEGY_LABELS),
        "by_underlying": _breakdown("ticker_symbol"),
    }


def format_trades_for_prompt(closed_trades: List[dict], limit: int = 20) -> str:
    """Compact preformatted trade lines for the LLM pattern prompt.

    All numbers are formatted here in Python; the LLM never computes.
    """
    lines = []
    for t in closed_trades[:limit]:
        pnl = float(t.get("realized_pnl") or 0.0)
        sign = "+" if pnl >= 0 else "-"
        try:
            held = holding_days(_parse_dt(t["opened_at"]), _parse_dt(t["closed_at"]))
            held_str = f", held {held}d"
        except (KeyError, TypeError, ValueError):
            held_str = ""
        lines.append(
            f"- {t.get('ticker_symbol', '?')} {t.get('strategy', '?')} "
            f"K={t.get('strike_price', '?')} exp {t.get('expiration_date', '?')}, "
            f"{t.get('quantity', '?')}x, in {float(t.get('premium') or 0):.2f} "
            f"out {float(t.get('exit_price') or 0):.2f}, "
            f"P/L {sign}${abs(pnl):,.0f} ({t.get('status', 'closed')}){held_str}"
        )
    return "\n".join(lines)
