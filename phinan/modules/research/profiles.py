"""Profile-aware research insights.

Profile definitions live in phinan/config/profiles.py (single source of
truth); they are re-exported here for existing callers.
"""

from ...config.profiles import PROFILES, UserProfile, get_profile

__all__ = [
    "PROFILES",
    "UserProfile",
    "get_profile",
    "get_insights",
    "get_conservative_insights",
    "get_aggressive_insights",
    "get_standard_insights",
]


def get_insights(
    profile_key: str,
    ticker_info: dict,
    price_range: dict,
    recent_news: list,
    analyst_data: dict,
) -> list[str]:
    """Generate insights for the given profile key (defaults to standard)."""
    if profile_key == "conservative":
        return get_conservative_insights(ticker_info, price_range, analyst_data)
    if profile_key == "aggressive":
        return get_aggressive_insights(
            ticker_info, price_range, recent_news, analyst_data
        )
    return get_standard_insights(ticker_info, price_range, recent_news, analyst_data)


def get_conservative_insights(ticker_info: dict, price_range: dict, analyst_data: dict) -> list[str]:
    """Generate insights for the Conservative strategy.
    
    Focuses on: dividend yields, range positioning for covered calls, quality metrics.
    """
    insights = []
    
    # Dividend yield for margin strategy (target > 3%)
    div_yield = ticker_info.get("dividend_yield", 0) or 0
    if div_yield >= 0.05:
        insights.append(f" Strong dividend ({div_yield:.1%}) - exceeds 3% margin target")
    elif div_yield >= 0.03:
        insights.append(f" Dividend ({div_yield:.1%}) meets margin strategy threshold")
    elif div_yield > 0:
        insights.append(f" Dividend ({div_yield:.1%}) below 3% margin target")
    else:
        insights.append(" No dividend - not ideal for margin strategy")
    
    # Range position for covered calls
    pct = price_range.get("percent_of_range", 0.5)
    if pct > 0.75:
        insights.append(" Near range high - good candidate for selling covered calls")
    elif pct < 0.25:
        insights.append(" Near range low - potential put-buying opportunity for entry")
    else:
        insights.append(f"Mid-range ({pct:.0%}) - wait for better entry/exit point")
    
    # Analyst consensus
    rating = analyst_data.get("rating", "").lower() if analyst_data.get("rating") else ""
    if rating in ["buy", "strong buy"]:
        insights.append(f" Analyst consensus: {rating.title()} - supports ownership thesis")
    elif rating in ["sell", "strong sell"]:
        insights.append(f" Analyst consensus: {rating.title()} - reconsider ownership")
    
    return insights


def get_aggressive_insights(ticker_info: dict, price_range: dict, recent_news: list, analyst_data: dict) -> list[str]:
    """Generate insights for the Aggressive strategy.
    
    Focuses on: momentum, news flow, analyst upgrades, directional opportunities.
    """
    insights = []
    
    # News flow momentum
    if len(recent_news) >= 3:
        insights.append(" High news volume - active story, increased volatility likely")
    elif len(recent_news) == 0:
        insights.append("Low news flow - may lack near-term catalyst")
    
    # Range position for directional plays
    pct = price_range.get("percent_of_range", 0.5)
    if pct < 0.3:
        insights.append(" Low in range - potential bullish setup for calls")
    elif pct > 0.7:
        insights.append(" High in range - consider puts or wait for pullback")
    else:
        insights.append(f"Mid-range ({pct:.0%}) - look for breakout confirmation")
    
    # Target price upside
    target = analyst_data.get("target_price")
    current = ticker_info.get("current_price")
    if target and current:
        upside = (target - current) / current
        if upside > 0.15:
            insights.append(f" Analyst target implies {upside:.0%} upside - supports bullish thesis")
        elif upside < -0.10:
            insights.append(f" Analyst target implies {abs(upside):.0%} downside")
    
    # Number of analysts coverage
    num_analysts = analyst_data.get("num_analysts", 0)
    if num_analysts and num_analysts > 10:
        insights.append(f"Well-covered ({num_analysts} analysts) - consensus more reliable")
    elif num_analysts and num_analysts < 3:
        insights.append(f"Low coverage ({num_analysts} analysts) - higher uncertainty")
    
    return insights


def get_standard_insights(ticker_info: dict, price_range: dict, recent_news: list, analyst_data: dict) -> list[str]:
    """Generate balanced insights for comprehensive analysis.
    
    Shows key points from both strategies for educational comparison.
    """
    insights = []
    
    # Range position
    pct = price_range.get("percent_of_range", 0.5)
    insights.append(f"Currently at {pct:.0%} of range ({price_range.get('period', '3mo')})")
    
    # Dividend
    div_yield = ticker_info.get("dividend_yield", 0) or 0
    if div_yield > 0:
        insights.append(f"Dividend yield: {div_yield:.2%}")
    
    # Analyst summary
    rating = analyst_data.get("rating", "N/A")
    target = analyst_data.get("target_price")
    rating_str = rating.title() if rating else "N/A"
    target_str = f" | Target: ${target:.2f}" if target else ""
    insights.append(f"Analyst rating: {rating_str}{target_str}")
    
    # News count
    insights.append(f"Recent news items: {len(recent_news)}")
    
    return insights
