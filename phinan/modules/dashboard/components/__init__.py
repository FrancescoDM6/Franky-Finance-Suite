"""Dashboard UI components."""

from .alerts import news_alerts_card
from .brief import daily_brief_card
from .portfolio_summary import portfolio_mini_summary
from .quick_actions import quick_actions

__all__ = [
    "daily_brief_card",
    "news_alerts_card",
    "portfolio_mini_summary",
    "quick_actions",
]
