"""Options page - Options chain viewer and trade tracking.

Support weekly options plays with research and tracking.
"""

import reflex as rx

from ...components.layout import main_layout
from ...state.user_context import UserContextState
from ..portfolio.state import PortfolioState


def options_content() -> rx.Component:
    """Options page content."""
    return rx.vstack(
        rx.heading("Options Trading", size="6"),
        rx.text(
            "Options chain viewer, payoff diagrams, and trade logging.",
            size="2",
            color_scheme="gray",
        ),
        rx.divider(),
        rx.callout(
            rx.vstack(
                rx.text("Coming Soon", weight="bold"),
                rx.text(
                    "Track weekly options plays, analyze strategies, "
                    "and optimize your returns!",
                    size="2",
                ),
                spacing="2",
            ),
            icon="bar-chart-2",
            color_scheme="green",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Planned Features", size="4"),
                rx.unordered_list(
                    rx.list_item("Options chain viewer with IV and Greeks"),
                    rx.list_item("Payoff diagram generator for any strategy"),
                    rx.list_item("Trade logging and P&L tracking"),
                    rx.list_item("Win rate and pattern analysis"),
                    rx.list_item("Strategy suggestions based on research"),
                ),
                spacing="3",
                align="start",
            ),
            width="100%",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Supported Strategies", size="4"),
                rx.grid(
                    rx.badge("Long Call", color_scheme="green"),
                    rx.badge("Long Put", color_scheme="red"),
                    rx.badge("Covered Call", color_scheme="blue"),
                    rx.badge("Cash-Secured Put", color_scheme="purple"),
                    rx.badge("Vertical Spreads", color_scheme="orange"),
                    rx.badge("Iron Condor", color_scheme="gray"),
                    columns=rx.breakpoints({"0px": "2", "768px": "3"}),
                    spacing="2",
                ),
                spacing="3",
                align="start",
            ),
            width="100%",
        ),
        spacing="4",
        width="100%",
        max_width="800px",
    )


@rx.page(
    route="/options",
    title="Options | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions],
)
def options_page() -> rx.Component:
    """Options page."""
    return main_layout(options_content())
