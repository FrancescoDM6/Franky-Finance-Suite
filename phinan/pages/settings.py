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
                    ["Conservative", "Aggressive", "Standard"],
                    value=UserContextState.profile_display_name,
                    on_change=UserContextState.set_profile,
                    size="2",
                ),
                rx.text(
                    "Active timeframe: ",
                    UserContextState.timeframe_display_name,
                    size="1",
                    color_scheme="gray",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
        # Timeframe section
        rx.card(
            rx.vstack(
                rx.heading("Default Timeframe", size="4"),
                rx.text(
                    "Controls AI prompt context and default options expiration selection.",
                    size="2",
                    color_scheme="gray",
                ),
                rx.select(
                    ["1_week", "2_weeks", "1_2_months", "varies"],
                    value=UserContextState.typical_timeframe,
                    on_change=UserContextState.set_typical_timeframe,
                    size="2",
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
                        checked=UserContextState.dark_mode,
                        on_change=UserContextState.set_dark_mode,
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


@rx.page(
    route="/settings",
    title="Settings | Phinan Finance Suite",
    on_load=[AppState.set_page("settings"), UserContextState.load_context],
)
def settings_page() -> rx.Component:
    """Settings page."""
    return main_layout(settings_content())
