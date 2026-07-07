"""Prompt builders for the Options module.

Every number is preformatted here in Python; the LLM identifies patterns,
it never computes (per the "LLM extracts, Python calculates" rule).
"""

from typing import Any, Dict


def _pct(value: Any, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def _money(value: Any) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def build_pattern_prompt(
    performance: Dict[str, Any],
    trades_block: str,
    profile_name: str,
    profile_description: str,
) -> str:
    """Build the trade-pattern analysis prompt from computed facts only."""
    headline = "\n".join(
        [
            f"- Closed trades: {performance.get('trade_count', 0)} "
            f"({performance.get('win_count', 0)}W / {performance.get('loss_count', 0)}L)",
            f"- Win rate: {_pct(performance.get('win_rate'))}",
            f"- Average win: {_money(performance.get('avg_win'))} | "
            f"Average loss: -{_money(performance.get('avg_loss')).lstrip('+-')}",
            f"- Expectancy per trade: {_money(performance.get('expectancy'))}",
            f"- Total P/L: {_money(performance.get('total_pnl'))}",
            f"- Average holding period: {performance.get('avg_holding_days', 0)} days",
        ]
    )

    def _breakdown_block(rows) -> str:
        lines = []
        for row in rows or []:
            lines.append(
                f"- {row.get('label') or row.get('key')}: {row.get('count')} trades, "
                f"win rate {_pct(row.get('win_rate'))}, "
                f"total {_money(row.get('total_pnl'))}"
            )
        return "\n".join(lines) or "- (none)"

    return f"""You are Phin, a personal trading coach reviewing a user's logged
options trades.

USER PROFILE: {profile_name} - {profile_description}

HEADLINE METRICS (computed by the app - treat as ground truth):
{headline}

P/L BY STRATEGY:
{_breakdown_block(performance.get("by_strategy"))}

P/L BY UNDERLYING:
{_breakdown_block(performance.get("by_underlying"))}

RECENT CLOSED TRADES (most recent first):
{trades_block}

Write a short review (under 250 words, markdown):
1. Identify 2-3 specific patterns in what is working and what is losing
   money (strategy types, underlyings, holding periods, timing).
2. End with exactly ONE actionable change, clearly labeled.

STRICT RULES:
- Use ONLY the numbers provided above. Do not recompute, estimate, or
  invent any figure.
- Be specific and direct; reference actual strategies/tickers from the
  data. No generic trading advice.
- No greetings or filler; start directly with the content.
"""
