"""Options page - chain viewer, strategy preview, trade log, performance.

Layout per the design doc: chain viewer on top, trade form + strategy
preview in the middle, tabbed trade log (open/closed/performance) below.
"""

import reflex as rx

from ...components.layout import main_layout
from ...state.user_context import UserContextState
from .components import chain_card, preview_card, trade_form, trades_section
from .state import OptionsTradingState


def _performance_placeholder() -> rx.Component:
    return rx.center(
        rx.text(
            "Performance metrics appear once you close trades.",
            size="2",
            color="var(--pfs-text-muted)",
        ),
        padding="32px",
        width="100%",
    )


def options_content() -> rx.Component:
    """Options page content."""
    return rx.vstack(
        rx.heading("Options Trading", size="7"),
        rx.text(
            "Log trades, preview strategies, and track what actually works.",
            size="2",
            color="var(--pfs-text-muted)",
        ),
        chain_card(),
        rx.flex(
            rx.box(
                trade_form(),
                width=rx.breakpoints(initial="100%", md="380px"),
                flex_shrink="0",
            ),
            rx.box(
                preview_card(),
                flex="1",
                min_width="0",
            ),
            direction=rx.breakpoints(initial="column", md="row"),
            gap="16px",
            width="100%",
            align="start",
        ),
        trades_section(_performance_placeholder()),
        spacing="4",
        width="100%",
        max_width="1200px",
    )


@rx.page(
    route="/options",
    title="Options | Phinan Finance Suite",
    on_load=[UserContextState.load_context, OptionsTradingState.load_page],
)
def options_page() -> rx.Component:
    """Options page."""
    return main_layout(options_content())
