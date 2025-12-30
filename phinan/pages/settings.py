"""Settings page."""

import reflex as rx

from ..components.layout import main_layout
from ..state.app import AppState
from ..state.user_context import UserContextState


def settings_content() -> rx.Component:
    """Settings page content."""
    return rx.vstack(
        rx.heading("Settings", size="6"),
        rx.divider(),
        # Profile section
        rx.card(
            rx.vstack(
                rx.heading("Profile", size="4"),
                rx.text("Select your trading profile to customize the interface.", size="2", color_scheme="gray"),
                rx.select(
                    ["Papi", "Tio", "Franky"],
                    value=UserContextState.profile_display_name,
                    on_change=UserContextState.set_profile,
                    size="2",
                ),
                rx.text(
                    rx.cond(
                        UserContextState.active_profile == "papi",
                        "Conservative strategy - Options as entry/exit mechanism, 2-week timeframe",
                        rx.cond(
                            UserContextState.active_profile == "tio",
                            "Aggressive strategy - Directional plays, 1-2 month timeframe",
                            "Learning mode - All data visible for comprehensive understanding",
                        ),
                    ),
                    size="1",
                    color_scheme="gray",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
        # Range period section
        rx.card(
            rx.vstack(
                rx.heading("Default Range Period", size="4"),
                rx.text("Default time period for price range analysis.", size="2", color_scheme="gray"),
                rx.select(
                    ["1mo", "3mo", "6mo", "1y"],
                    value=UserContextState.default_range_period,
                    on_change=UserContextState.set_range_period,
                    size="2",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
        # Appearance section
        rx.card(
            rx.vstack(
                rx.heading("Appearance", size="4"),
                rx.hstack(
                    rx.text("Dark Mode", size="2"),
                    rx.switch(
                        checked=AppState.dark_mode,
                        on_change=AppState.toggle_dark_mode,
                    ),
                    justify="between",
                    width="100%",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
        spacing="4",
        width="100%",
        max_width="600px",
        align="start",
    )


@rx.page(route="/settings", title="Settings | Phinan Finance Suite", on_load=AppState.set_page("settings"))
def settings_page() -> rx.Component:
    """Settings page."""
    return main_layout(settings_content())
