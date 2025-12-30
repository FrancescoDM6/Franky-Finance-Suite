"""Portfolio page - Unified view of investment performance.

Aggregates data from options trades, positions, and structured notes.
"""

import reflex as rx

from ...components.layout import main_layout
from ...state.app import AppState


def portfolio_content() -> rx.Component:
    """Portfolio page content."""
    return rx.vstack(
        rx.heading("Portfolio", size="6"),
        rx.text(
            "Unified view of all your investments.",
            size="2",
            color_scheme="gray",
        ),
        rx.divider(),
        rx.callout(
            rx.vstack(
                rx.text("Coming Soon", weight="bold"),
                rx.text(
                    "Aggregate performance across options trades, stock positions, "
                    "and structured note investments.",
                    size="2",
                ),
                spacing="2",
            ),
            icon="pie-chart",
            color_scheme="purple",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Planned Features", size="4"),
                rx.unordered_list(
                    rx.list_item("Total portfolio value and P&L"),
                    rx.list_item("Allocation breakdown by asset type"),
                    rx.list_item("Performance charts over time"),
                    rx.list_item("Benchmark comparison (vs SPY, QQQ)"),
                    rx.list_item("Dividend income tracking"),
                    rx.list_item("Tax lot management"),
                ),
                spacing="3",
                align="start",
            ),
            width="100%",
        ),
        rx.text(
            "Note: Build the other modules first - Portfolio aggregates their data.",
            size="1",
            color_scheme="gray",
        ),
        spacing="4",
        width="100%",
        max_width="800px",
    )


@rx.page(route="/portfolio", title="Portfolio | Phinan Finance Suite", on_load=AppState.set_page("portfolio"))
def portfolio_page() -> rx.Component:
    """Portfolio page."""
    return main_layout(portfolio_content())
