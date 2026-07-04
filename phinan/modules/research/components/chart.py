"""Price chart component using Reflex recharts."""

import reflex as rx
from ....components.ui import card_header
from ..state import ResearchState


def price_chart() -> rx.Component:
    """Interactive price chart for stock history."""
    return rx.vstack(
        # Period selector
        rx.hstack(
            rx.text("Period:", size="2", color_scheme="gray"),
            rx.select(
                ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                value=ResearchState.chart_period,
                on_change=ResearchState.set_chart_period,
                size="1",
            ),
            spacing="2",
            align="center",
        ),
        # Chart
        rx.cond(
            ResearchState.has_chart_data,
            rx.recharts.line_chart(
                rx.recharts.line(
                    data_key="close",
                    stroke="var(--accent-9)",
                    stroke_width=2,
                    dot=False,
                ),
                rx.recharts.x_axis(
                    data_key="date",
                    tick_line=False,
                    axis_line=False,
                    tick_formatter="(value) => value.slice(5)",  # Show MM-DD
                ),
                rx.recharts.y_axis(
                    domain=["auto", "auto"],
                    tick_line=False,
                    axis_line=False,
                    tick_formatter="(value) => '$' + value.toFixed(0)",
                ),
                rx.recharts.cartesian_grid(
                    stroke_dasharray="3 3",
                    opacity=0.3,
                ),
                rx.recharts.graphing_tooltip(),
                data=ResearchState.price_history,
                width="100%",
                height=300,
                key=ResearchState.selected_ticker + ResearchState.chart_period + ResearchState.selected_tab, # Force re-render on tab change
            ),
            rx.center(
                rx.text("No chart data available", color_scheme="gray"),
                height="300px",
            ),
        ),
        spacing="3",
        width="100%",
    )


def chart_card() -> rx.Component:
    """Card wrapper for price chart."""
    return rx.card(
        rx.vstack(
            card_header(
                "Price History",
                rx.badge(
                    ResearchState.chart_period,
                    variant="soft",
                ),
            ),
            price_chart(),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
