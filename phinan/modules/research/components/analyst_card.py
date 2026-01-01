"""Analyst data card component."""

import reflex as rx
from ..state import ResearchState


def analyst_card() -> rx.Component:
    """Analyst consensus card."""
    return rx.card(
        rx.vstack(
            rx.heading("Analyst Consensus", size="4"),
            rx.divider(),
            rx.hstack(
                rx.vstack(
                    rx.text("Rating", size="1", color_scheme="gray"),
                    rx.badge(
                        rx.cond(
                            ResearchState.analyst_data.get("rating"),
                            ResearchState.analyst_data.get("rating"),
                            "N/A",
                        ),
                        color_scheme=rx.cond(
                            ResearchState.analyst_data.get("rating") == "buy",
                            "green",
                            rx.cond(
                                ResearchState.analyst_data.get("rating") == "sell",
                                "red",
                                "gray",
                            ),
                        ),
                        size="2",
                    ),
                    align="center",
                ),
                rx.vstack(
                    rx.text("Target Price", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.analyst_data.get("target_price"),
                            rx.text("$", ResearchState.analyst_data.get("target_price")),
                            "N/A",
                        ),
                        size="3",
                        weight="bold",
                    ),
                    rx.cond(
                        ResearchState.analyst_data.get("target_price") & ResearchState.current_price,
                        rx.badge(
                            rx.text(
                                ResearchState.upside_percentage,
                                "% Upside",
                            ),
                            color_scheme="green",
                            variant="soft",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    align="center",
                ),
                rx.vstack(
                    rx.text("# Analysts", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.analyst_data.get("num_analysts"),
                            ResearchState.analyst_data.get("num_analysts"),
                            "N/A",
                        ),
                        size="3",
                        weight="medium",
                    ),
                    align="center",
                ),
                justify="between",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
