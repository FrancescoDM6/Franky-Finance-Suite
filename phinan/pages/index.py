"""Dashboard route and page composition."""

import reflex as rx

from ..components.layout import main_layout
from ..modules.dashboard.components import (
    daily_brief_card,
    news_alerts_card,
    portfolio_mini_summary,
    quick_actions,
)
from ..modules.dashboard.state import DailyBriefState
from ..modules.portfolio.state import PortfolioState
from ..state.user_context import UserContextState


def dashboard_content() -> rx.Component:
    """Compose the home dashboard."""
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.heading("Welcome back", size="6"),
                rx.badge(
                    UserContextState.profile_display_name,
                    variant="soft",
                    size="2",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.badge(
                rx.hstack(
                    rx.icon("activity", size=14),
                    rx.text("Markets Open", size="1"),
                    spacing="1",
                ),
                color_scheme="green",
                variant="soft",
            ),
            width="100%",
            align="center",
        ),
        rx.divider(),
        rx.grid(
            daily_brief_card(),
            rx.hstack(
                portfolio_mini_summary(),
                quick_actions(),
                spacing="4",
                width="100%",
            ),
            columns=rx.breakpoints({"0px": "1", "768px": "2"}),
            spacing="4",
            width="100%",
        ),
        news_alerts_card(),
        spacing="4",
        width="100%",
        align="start",
    )


@rx.page(
    route="/",
    title="Home | Phinan Finance Suite",
    on_load=[
        UserContextState.load_context,
        PortfolioState.load_positions,
        DailyBriefState.generate_brief,
    ],
)
def index() -> rx.Component:
    """Render the home page."""
    return main_layout(dashboard_content())
