"""Options snapshot card component."""

import reflex as rx
from ..state import ResearchState


def expiration_selector() -> rx.Component:
    """Dropdown for expiration selection."""
    return rx.select.root(
        rx.select.trigger(
            placeholder="Select Expiration",
        ),
        rx.select.content(
            rx.foreach(
                ResearchState.options_expirations,
                lambda exp: rx.select.item(exp, value=exp),
            ),
        ),
        value=ResearchState.selected_expiration,
        on_change=ResearchState.set_options_expiration,
        size="2",
    )


def options_metadata_row() -> rx.Component:
    """ATM IV, days to expiry, current price row."""
    return rx.hstack(
        rx.hstack(
            rx.text("ATM IV:", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.options_atm_iv_pct,
                size="2",
                weight="bold",
            ),
            spacing="1",
            align="center",
        ),
        rx.divider(orientation="vertical", size="1"),
        rx.hstack(
            rx.text("Days:", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.options_days_to_expiry,
                size="2",
                weight="bold",
            ),
            spacing="1",
            align="center",
        ),
        rx.divider(orientation="vertical", size="1"),
        rx.hstack(
            rx.text("Price:", size="1", color_scheme="gray"),
            rx.text(
                "$", ResearchState.current_price,
                size="2",
                weight="bold",
                color="var(--blue-11)",
            ),
            spacing="1",
            align="center",
        ),
        justify="start",
        spacing="4",
        padding_y="2",
        wrap="wrap",
    )


def options_table_header() -> rx.Component:
    """Column headers for options table."""
    return rx.hstack(
        rx.text("Strike", size="1", weight="bold", width="70px"),
        rx.text("Bid", size="1", weight="bold", width="55px", text_align="right"),
        rx.text("Ask", size="1", weight="bold", width="55px", text_align="right"),
        rx.text("OI", size="1", weight="bold", width="55px", text_align="right"),
        rx.text("IV", size="1", weight="bold", width="45px", text_align="right"),
        rx.box(width="80px"),  # Annotation column
        spacing="2",
        width="100%",
        min_width="420px",
        padding_x="2",
        padding_y="1",
        background="var(--gray-2)",
        border_radius="4px",
    )


def option_row(option: dict) -> rx.Component:
    """Single option row."""
    return rx.hstack(
        # Strike with ATM highlight
        rx.text(
            "$", option["strike"],
            size="2",
            weight=rx.cond(option["is_atm"], "bold", "regular"),
            color=rx.cond(option["is_atm"], "var(--accent-11)", "inherit"),
            width="70px",
        ),
        rx.text(
            "$", option["bid"],
            size="2",
            width="55px",
            text_align="right",
        ),
        rx.text(
            "$", option["ask"],
            size="2",
            width="55px",
            text_align="right",
        ),
        rx.text(
            option["oi"],
            size="1",
            color_scheme="gray",
            width="55px",
            text_align="right",
        ),
        rx.text(
            option["iv_pct"],
            size="1",
            color_scheme="gray",
            width="45px",
            text_align="right",
        ),
        # Annotation badge
        rx.cond(
            option["annotation"] != "",
            rx.badge(
                option["annotation"],
                size="1",
                variant="soft",
                color_scheme=rx.match(
                    option["annotation"],
                    ("ATM", "blue"),
                    ("Range High", "red"),
                    ("Range Low", "green"),
                    ("Target", "purple"),
                    ("Round", "gray"),
                    "gray",
                ),
            ),
            rx.box(width="80px"),
        ),
        spacing="2",
        width="100%",
        min_width="420px",
        padding_x="2",
        padding_y="1",
        _hover={"background": "var(--gray-2)"},
    )


def calls_section() -> rx.Component:
    """Calls section with header and rows."""
    return rx.vstack(
        rx.text("CALLS", size="2", weight="bold", color="var(--green-11)"),
        options_table_header(),
        rx.foreach(
            ResearchState.options_calls,
            option_row,
        ),
        spacing="1",
        width="100%",
    )


def puts_section() -> rx.Component:
    """Puts section with header and rows."""
    return rx.vstack(
        rx.text("PUTS", size="2", weight="bold", color="var(--red-11)"),
        options_table_header(),
        rx.foreach(
            ResearchState.options_puts,
            option_row,
        ),
        spacing="1",
        width="100%",
    )


def profile_hint() -> rx.Component:
    """Profile-specific trading hint based on range position."""
    return rx.cond(
        ResearchState.is_near_range_high,
        # Near range high
        rx.callout(
            rx.hstack(
                rx.icon("lightbulb", size=14),
                rx.text(
                    "Near range high - covered calls may offer good premium capture.",
                    size="1",
                ),
                spacing="2",
                align="center",
            ),
            color_scheme="amber",
            variant="soft",
            size="1",
        ),
        rx.cond(
            ResearchState.is_near_range_low,
            # Near range low
            rx.callout(
                rx.hstack(
                    rx.icon("lightbulb", size=14),
                    rx.text(
                        "Near range low - cash-secured puts for entry worth evaluating.",
                        size="1",
                    ),
                    spacing="2",
                    align="center",
                ),
                color_scheme="green",
                variant="soft",
                size="1",
            ),
            rx.fragment(),
        ),
    )


def options_card() -> rx.Component:
    """Main options snapshot card component."""
    return rx.card(
        rx.vstack(
            # Header with expiration selector
            rx.hstack(
                rx.hstack(
                    rx.icon("bar-chart-4", size=18),
                    rx.heading("Options Snapshot", size="4"),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                expiration_selector(),
                width="100%",
                align="center",
            ),
            rx.divider(),
            # Loading state
            rx.cond(
                ResearchState.options_loading,
                rx.center(
                    rx.spinner(size="2"),
                    padding="4",
                ),
                # Error state
                rx.cond(
                    ResearchState.options_error != "",
                    rx.callout(
                        ResearchState.options_error,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    # Data state
                    rx.cond(
                        ResearchState.has_options_data,
                        rx.vstack(
                            options_metadata_row(),
                            rx.divider(),
                            rx.box(
                                calls_section(),
                                overflow_x="auto",
                                width="100%",
                            ),
                            rx.divider(),
                            rx.box(
                                puts_section(),
                                overflow_x="auto",
                                width="100%",
                            ),
                            rx.divider(),
                            profile_hint(),
                            spacing="3",
                            width="100%",
                        ),
                        # No data / no selection state
                        rx.cond(
                            ResearchState.options_expirations.length() > 0,
                            rx.center(
                                rx.text(
                                    "Select an expiration to view options.",
                                    size="2",
                                    color_scheme="gray",
                                ),
                                padding="4",
                            ),
                            rx.center(
                                rx.text(
                                    "No options available for this ticker.",
                                    size="2",
                                    color_scheme="gray",
                                ),
                                padding="4",
                            ),
                        ),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
