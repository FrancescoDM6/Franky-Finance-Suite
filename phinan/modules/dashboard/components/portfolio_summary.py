"""Dashboard portfolio summary components."""

import reflex as rx

from ....components.ui import content_card
from ...portfolio.state import PortfolioState


def portfolio_mini_summary() -> rx.Component:
    """Render a compact portfolio summary card."""
    return content_card(
        rx.vstack(
            rx.hstack(
                rx.icon("briefcase", size=16),
                rx.heading("Portfolio", size="4"),
                rx.spacer(),
                rx.link(rx.text("View all", size="1"), href="/portfolio"),
                width="100%",
                align="center",
            ),
            rx.divider(),
            rx.cond(
                PortfolioState.has_positions,
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.text("Total Value", size="1", color_scheme="gray"),
                            rx.text(
                                PortfolioState.fmt_total_value,
                                size="4",
                                weight="bold",
                            ),
                            spacing="0",
                            align="start",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.text("P/L", size="1", color_scheme="gray"),
                            rx.text(
                                PortfolioState.fmt_total_pl_pct,
                                size="3",
                                weight="bold",
                                color=rx.cond(
                                    PortfolioState.total_gain_loss_percent >= 0,
                                    "var(--green-11)",
                                    "var(--red-11)",
                                ),
                            ),
                            spacing="0",
                            align="end",
                        ),
                        width="100%",
                    ),
                    rx.text(
                        PortfolioState.positions.length(),
                        " positions",
                        size="1",
                        color_scheme="gray",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.center(
                    rx.text("No positions yet", size="2", color_scheme="gray"),
                    padding="4",
                ),
            ),
            spacing="2",
            width="100%",
        ),
        width="100%",
    )
