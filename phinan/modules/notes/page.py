"""Notes page - structured note decomposition and analysis.

Layout: upload zone on top, editable terms form on the left, simulation
results (fee breakdown, risk scenarios) on the right.
"""

import reflex as rx

from ...components.layout import main_layout
from ...modules.portfolio.state import PortfolioState
from ...state.user_context import UserContextState
from .components import (
    alternatives_card,
    mc_chart,
    risk_card,
    terms_form,
    upload_card,
    valuation_card,
)
from .state import NotesState


def _empty_results_hint() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon("file-search", size=40, color="var(--gray-8)"),
            rx.text(
                "Upload a term sheet or fill in the terms, then click "
                "Analyze Note.",
                size="2",
                color="var(--pfs-text-muted)",
                text_align="center",
            ),
            rx.text(
                "The analysis decomposes the note into fair value, embedded "
                "fees, and simulated risk scenarios.",
                size="1",
                color="var(--pfs-text-muted)",
                text_align="center",
            ),
            spacing="2",
            align="center",
        ),
        padding="60px",
        width="100%",
    )


def _results_column() -> rx.Component:
    return rx.cond(
        NotesState.has_analysis,
        rx.vstack(
            valuation_card(),
            risk_card(),
            mc_chart(),
            rx.cond(NotesState.has_alternatives, alternatives_card(), rx.fragment()),
            spacing="4",
            width="100%",
        ),
        _empty_results_hint(),
    )


def notes_content() -> rx.Component:
    """Main notes page content."""
    return rx.vstack(
        rx.heading("Structured Notes", size="7"),
        rx.text(
            "Decompose bank products into fair value, fees, and risk.",
            size="2",
            color="var(--pfs-text-muted)",
        ),
        upload_card(),
        rx.flex(
            rx.box(terms_form(), width=rx.breakpoints(initial="100%", md="360px"), flex_shrink="0"),
            rx.box(_results_column(), flex="1", min_width="0"),
            direction=rx.breakpoints(initial="column", md="row"),
            gap="16px",
            width="100%",
            align="start",
        ),
        spacing="4",
        width="100%",
        max_width="1200px",
    )


@rx.page(
    route="/notes",
    title="Notes | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions],
)
def notes_page() -> rx.Component:
    """Notes page."""
    return main_layout(notes_content())
