"""Notes page - Structured note analysis.

Decompose opaque bank products to reveal actual fees, risks, and opportunity costs.
"""

import reflex as rx

from ...components.layout import main_layout
from ...state.app import AppState
from ...state.user_context import UserContextState
from ..portfolio.state import PortfolioState


def notes_content() -> rx.Component:
    """Notes page content."""
    return rx.vstack(
        rx.heading("Structured Notes Analyzer", size="6"),
        rx.text(
            "Decompose structured notes to reveal true risk/reward.",
            size="2",
            color_scheme="gray",
        ),
        rx.divider(),
        rx.callout(
            rx.vstack(
                rx.text("Coming Soon", weight="bold"),
                rx.text(
                    "This module will help analyze structured notes from private banks, "
                    "revealing embedded fees, risk scenarios, and comparisons to simpler alternatives.",
                    size="2",
                ),
                spacing="2",
            ),
            icon="file-text",
            color_scheme="blue",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Planned Features", size="4"),
                rx.unordered_list(
                    rx.list_item("Fee decomposition and true yield calculation"),
                    rx.list_item("Monte Carlo simulation of outcomes"),
                    rx.list_item("Risk scenario modeling (barrier breach, autocall)"),
                    rx.list_item("Comparison to alternatives (covered calls, bonds)"),
                    rx.list_item("PDF term sheet parsing with LLM extraction"),
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
    route="/notes",
    title="Notes | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions],
)
def notes_page() -> rx.Component:
    """Notes page."""
    return main_layout(notes_content())
