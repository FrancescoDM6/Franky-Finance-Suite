"""User profiles for research emphasis.

Different profiles emphasize different aspects of research
based on trading strategy.
"""

from dataclasses import dataclass


@dataclass
class UserProfile:
    """User profile configuration."""

    name: str
    strategy_type: str  # "conservative", "aggressive", "learning"
    typical_timeframe: str  # "2_weeks", "1_2_months", "varies"
    default_range_period: str  # "1mo", "3mo", "6mo", "1y"
    emphasis: list[str]  # Sections to highlight
    description: str


PROFILES = {
    "papi": UserProfile(
        name="Papi",
        strategy_type="conservative",
        typical_timeframe="2_weeks",
        default_range_period="3mo",
        emphasis=["dividend_yield", "cost_basis", "range_high_calls", "quality_check"],
        description="Options as entry/exit mechanism. Focus on quality stocks, "
        "dividend yield for margin strategy, covered calls near range high.",
    ),
    "tio": UserProfile(
        name="Tio",
        strategy_type="aggressive",
        typical_timeframe="1_2_months",
        default_range_period="6mo",
        emphasis=["momentum", "analyst_deep_dive", "iv_analysis", "news_sentiment"],
        description="Traditional risk-taking with deeper research. "
        "Longer timeframes, momentum-focused, uses structured notes for long-term.",
    ),
    "franky": UserProfile(
        name="Franky",
        strategy_type="learning",
        typical_timeframe="varies",
        default_range_period="6mo",
        emphasis=["all"],  # Show everything while learning
        description="Learning mode - show all data for comprehensive understanding. "
        "Building systematic approach to beat Papi and Tio's returns.",
    ),
}


def get_profile(name: str) -> UserProfile:
    """Get a profile by name, defaulting to Franky."""
    return PROFILES.get(name.lower(), PROFILES["franky"])
