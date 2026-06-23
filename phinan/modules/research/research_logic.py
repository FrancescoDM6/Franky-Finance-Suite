"""Pure computation helpers for the Research module.

These functions hold no Reflex state and take plain inputs so they can be unit
tested directly. They operate on dicts and duck-typed news objects (anything
with sentiment_label / sentiment_score attributes), avoiding an import of the
NewsItem model and the import cycle that would create.
"""

from typing import Any


def compute_quality_check(ticker_info: dict[str, Any]) -> dict[str, Any]:
    """Compute a quality assessment from ticker fundamentals.

    Returns a dict with the raw fundamentals, warning flags, and an overall
    Pass/Review verdict (Review when two or more flags trip).
    """
    flags = []

    # Check dividend yield for margin strategy (target > 3%)
    div_yield = ticker_info.get("dividend_yield") or 0
    if div_yield < 0.03:
        flags.append("Dividend below 3% margin target")

    # Check profitability
    profit_margin = ticker_info.get("profit_margin") or 0
    if profit_margin < 0.1:
        flags.append("Low profit margin (<10%)")

    # Check debt
    debt_ratio = ticker_info.get("debt_to_equity") or 0
    if debt_ratio > 2:
        flags.append("High debt/equity ratio (>2)")

    # Check P/E
    pe = ticker_info.get("pe_ratio")
    if pe and pe > 50:
        flags.append("High P/E ratio (>50)")
    elif pe and pe < 0:
        flags.append("Negative P/E (unprofitable)")

    return {
        "industry": ticker_info.get("industry", "Unknown"),
        "pe_ratio": ticker_info.get("pe_ratio"),
        "profit_margin": profit_margin,
        "debt_to_equity": debt_ratio,
        "dividend_yield": div_yield,
        "flags": flags,
        "overall": "Pass" if len(flags) < 2 else "Review",
    }


def compute_aggregate_sentiment(recent_news: list) -> dict[str, Any]:
    """Aggregate sentiment across news items.

    Accepts any iterable of objects exposing sentiment_label (str) and
    sentiment_score (float). Returns {} when there are no items.
    """
    if not recent_news:
        return {}

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    total_score = 0.0

    for item in recent_news:
        label = item.sentiment_label
        if label in counts:
            counts[label] += 1
        total_score += item.sentiment_score

    total = len(recent_news)
    dominant = max(counts, key=counts.get) if total > 0 else "neutral"
    avg_confidence = total_score / total if total > 0 else 0.5

    return {
        "dominant": dominant,
        "counts": counts,
        "average_confidence": round(avg_confidence, 2),
        "total": total,
    }
