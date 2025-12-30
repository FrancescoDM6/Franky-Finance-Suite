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
            # Upside/downside calculation
            rx.cond(
                ResearchState.analyst_data.get("target_price"),
                rx.box(
                    rx.text(
                        rx.cond(
                            ResearchState.current_price,
                            rx.text(
                                "Upside to target: ",
                                rx.text(
                                    ((ResearchState.analyst_data.get("target_price", 0).to(float) / ResearchState.current_price - 1) * 100).to(int),
                                    "%",
                                    weight="bold",
                                    as_="span",
                                ),
                                as_="span",
                            ),
                            "",
                        ),
                        size="1",
                        color_scheme="gray",
                    ),
                    padding_top="2",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
