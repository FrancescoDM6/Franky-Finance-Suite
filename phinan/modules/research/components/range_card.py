"""Price range card component."""

import reflex as rx
from ..state import ResearchState


def range_card() -> rx.Component:
    """Price range visualization card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Price Range", size="4"),
                rx.badge(ResearchState.range_period, variant="soft"),
                rx.spacer(),
                rx.badge(
                    ResearchState.range_position_label,
                    color_scheme=ResearchState.range_position_color,
                    variant="soft",
                ),
                width="100%",
            ),
            rx.divider(),
            # Range stats
            rx.grid(
                rx.vstack(
                    rx.text("High", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.price_range.get("high"),
                            rx.text("$", ResearchState.fmt_range_high),
                            "N/A",
                        ),
                        size="3",
                        weight="bold",
                    ),
                    align="center",
                ),
                rx.vstack(
                    rx.text("Current", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.price_range.get("current"),
                            rx.text("$", ResearchState.fmt_range_current),
                            "N/A",
                        ),
                        size="3",
                        weight="bold",
                        color_scheme="blue",
                    ),
                    align="center",
                ),
                rx.vstack(
                    rx.text("Low", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.price_range.get("low"),
                            rx.text("$", ResearchState.fmt_range_low),
                            "N/A",
                        ),
                        size="3",
                        weight="bold",
                    ),
                    align="center",
                ),
                columns="3",
                width="100%",
            ),
            # Progress bar
            rx.box(
                rx.progress(
                    value=(ResearchState.price_range.get("percent_of_range", 0.5).to(float) * 100).to(int),
                    color_scheme=ResearchState.range_position_color,
                ),
                width="100%",
                padding_y="2",
            ),
            rx.text(
                rx.cond(
                    ResearchState.price_range.get("percent_of_range"),
                    rx.text(
                        ResearchState.fmt_range_percent,
                        " of range",
                    ),
                    "N/A",
                ),
                size="1",
                color_scheme="gray",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
