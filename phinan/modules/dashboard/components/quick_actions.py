"""Dashboard quick action components."""

import reflex as rx

from ....components.ui import content_card
from ...portfolio.state import PortfolioState


def quick_add_position_dialog() -> rx.Component:
    """Render the dashboard add-position dialog."""
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=16),
                "Add Position",
                variant="soft",
                color_scheme="green",
                size="2",
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("Add Position"),
            rx.dialog.description("Add a new stock to your portfolio."),
            rx.vstack(
                rx.input(
                    placeholder="Ticker (e.g., AAPL)",
                    value=PortfolioState.form_ticker,
                    on_change=PortfolioState.set_form_ticker,
                    width="100%",
                ),
                rx.input(
                    placeholder="Quantity",
                    type="number",
                    value=PortfolioState.form_quantity,
                    on_change=PortfolioState.set_form_quantity,
                    width="100%",
                ),
                rx.input(
                    placeholder="Cost per share",
                    type="number",
                    value=PortfolioState.form_cost_basis,
                    on_change=PortfolioState.set_form_cost_basis,
                    width="100%",
                ),
                rx.cond(
                    PortfolioState.error_message != "",
                    rx.callout(
                        PortfolioState.error_message,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel", variant="soft", color_scheme="gray")
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Add",
                            on_click=PortfolioState.add_position,
                            color_scheme="green",
                        )
                    ),
                    spacing="2",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                padding_top="2",
            ),
            style={"max_width": "400px"},
        ),
    )


def quick_actions() -> rx.Component:
    """Render dashboard navigation and portfolio actions."""
    return content_card(
        rx.vstack(
            rx.hstack(
                rx.icon("zap", size=16),
                rx.heading("Quick Actions", size="4"),
                spacing="2",
                align="center",
            ),
            rx.divider(),
            rx.grid(
                rx.link(
                    rx.button(
                        rx.icon("search", size=16),
                        "Research",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/research",
                    width="100%",
                ),
                quick_add_position_dialog(),
                rx.link(
                    rx.button(
                        rx.icon("bar-chart-4", size=16),
                        "Options",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/options",
                    width="100%",
                ),
                rx.link(
                    rx.button(
                        rx.icon("file-text", size=16),
                        "Notes",
                        variant="soft",
                        size="2",
                        width="100%",
                    ),
                    href="/notes",
                    width="100%",
                ),
                columns="2",
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
