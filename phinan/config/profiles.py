"""User profile definitions - single source of truth.

Consumed by:
- phinan/state/user_context.py (profile defaults on switch)
- phinan/modules/research/profiles.py (insight generation + synthesis context)
"""

from dataclasses import dataclass


@dataclass
class UserProfile:
    """User profile configuration."""

    name: str
    strategy_type: str  # "conservative", "aggressive", "learning"
    risk_tolerance: str  # "conservative", "aggressive", "learning"
    typical_strategy: str  # "entry_exit", "directional", "varies"
    typical_timeframe: str  # "2_weeks", "1_2_months", "varies"
    default_range_period: str  # "1mo", "3mo", "6mo", "1y"
    emphasis: list[str]  # Sections to highlight
    description: str


PROFILES = {
    "conservative": UserProfile(
        name="Conservative",
        strategy_type="conservative",
        risk_tolerance="conservative",
        typical_strategy="entry_exit",
        typical_timeframe="2_weeks",
        default_range_period="3mo",
        emphasis=["dividend_yield", "cost_basis", "range_high_calls", "quality_check"],
        description="Options as entry/exit mechanism. Focus on quality stocks, "
        "dividend yield for margin strategy, covered calls near range high.",
    ),
    "aggressive": UserProfile(
        name="Aggressive",
        strategy_type="aggressive",
        risk_tolerance="aggressive",
        typical_strategy="directional",
        typical_timeframe="1_2_months",
        default_range_period="6mo",
        emphasis=["momentum", "analyst_deep_dive", "iv_analysis", "news_sentiment"],
        description="Traditional risk-taking with deeper research. "
        "Longer timeframes, momentum-focused, uses structured notes for long-term.",
    ),
    "standard": UserProfile(
        name="Standard",
        strategy_type="learning",
        risk_tolerance="learning",
        typical_strategy="varies",
        typical_timeframe="varies",
        default_range_period="6mo",
        emphasis=["all"],  # Show everything for comprehensive understanding
        description="Balanced mode - show all data for comprehensive understanding. "
        "Building systematic approach with full visibility into all metrics.",
    ),
}


def get_profile(name: str) -> UserProfile:
    """Get a profile by name, defaulting to Standard."""
    return PROFILES.get(name.lower(), PROFILES["standard"])
