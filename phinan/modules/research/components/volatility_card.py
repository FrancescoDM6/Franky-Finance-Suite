"""Volatility analysis card component.

Displays GARCH forecast vs implied volatility comparison,
with user-selectable forecast horizon.
"""

import reflex as rx
from ..state import ResearchState


def horizon_selector() -> rx.Component:
    """Dropdown for forecast horizon selection."""
    return rx.select.root(
        rx.select.trigger(
            placeholder="Select Horizon",
        ),
        rx.select.content(
            rx.select.item("1 Week (5 days)", value="5"),
            rx.select.item("1 Month (21 days)", value="21"),
            rx.select.item("3 Months (63 days)", value="63"),
        ),
        value=ResearchState.volatility_horizon,
        on_change=ResearchState.set_volatility_horizon,
        size="2",
    )


def volatility_comparison_row() -> rx.Component:
    """Row comparing GARCH vs IV with ratio."""
    return rx.hstack(
        # GARCH Vol
        rx.vstack(
            rx.text("GARCH", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.volatility_garch_vol_pct,
                size="3",
                weight="bold",
            ),
            spacing="1",
            align="center",
        ),
        rx.divider(orientation="vertical", size="2"),
        # Implied Vol
        rx.vstack(
            rx.text("IV", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.volatility_implied_vol_pct,
                size="3",
                weight="bold",
            ),
            spacing="1",
            align="center",
        ),
        rx.divider(orientation="vertical", size="2"),
        # Ratio
        rx.vstack(
            rx.text("Ratio", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.volatility_iv_garch_ratio_fmt,
                size="3",
                weight="bold",
                color=rx.match(
                    ResearchState.volatility_interpretation_color,
                    ("amber", "var(--amber-11)"),
                    ("green", "var(--green-11)"),
                    ("blue", "var(--blue-11)"),
                    "inherit",
                ),
            ),
            spacing="1",
            align="center",
        ),
        rx.divider(orientation="vertical", size="2"),
        # Difference
        rx.vstack(
            rx.text("Diff", size="1", color_scheme="gray"),
            rx.text(
                ResearchState.volatility_iv_garch_diff_pct,
                size="2",
                weight="medium",
            ),
            spacing="1",
            align="center",
        ),
        justify="between",
        spacing="4",
        padding_y="3",
        width="100%",
    )


def expected_range_row() -> rx.Component:
    """Row showing GARCH-based expected price range."""
    return rx.hstack(
        rx.text("Expected Range:", size="2", color_scheme="gray"),
        rx.hstack(
            rx.text(
                "$",
                ResearchState.volatility_range_low.to(int),
                size="2",
                weight="medium",
                color="var(--green-11)",
            ),
            rx.text("-", size="2", color_scheme="gray"),
            rx.text(
                "$",
                ResearchState.volatility_range_high.to(int),
                size="2",
                weight="medium",
                color="var(--red-11)",
            ),
            spacing="1",
        ),
        rx.text(
            "(68% confidence)",
            size="1",
            color_scheme="gray",
        ),
        justify="start",
        spacing="3",
        align="center",
    )


def interpretation_badge() -> rx.Component:
    """Badge showing IV interpretation."""
    return rx.cond(
        ResearchState.volatility_interpretation != "",
        rx.callout(
            rx.hstack(
                rx.icon("info", size=14),
                rx.text(
                    ResearchState.volatility_interpretation,
                    size="1",
                ),
                spacing="2",
                align="center",
            ),
            color_scheme=ResearchState.volatility_interpretation_color,
            variant="soft",
            size="1",
        ),
        rx.fragment(),
    )


def volatility_card() -> rx.Component:
    """Main volatility analysis card component."""
    return rx.card(
        rx.vstack(
            # Header with horizon selector
            rx.hstack(
                rx.hstack(
                    rx.icon("activity", size=18),
                    rx.heading("Volatility Analysis", size="4"),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                horizon_selector(),
                width="100%",
                align="center",
            ),
            rx.divider(),
            # Loading state
            rx.cond(
                ResearchState.volatility_loading,
                rx.center(
                    rx.spinner(size="2"),
                    padding="4",
                ),
                # Error state
                rx.cond(
                    ResearchState.volatility_error != "",
                    rx.callout(
                        ResearchState.volatility_error,
                        icon="circle-alert",
                        color_scheme="orange",
                        size="1",
                    ),
                    # Data state
                    rx.cond(
                        ResearchState.volatility_available,
                        rx.vstack(
                            volatility_comparison_row(),
                            rx.divider(),
                            expected_range_row(),
                            rx.divider(),
                            interpretation_badge(),
                            spacing="3",
                            width="100%",
                        ),
                        # No data state
                        rx.center(
                            rx.text(
                                "Volatility analysis requires options data.",
                                size="2",
                                color_scheme="gray",
                            ),
                            padding="4",
                        ),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
