"""Home page / Dashboard."""

import reflex as rx

from ..components.layout import main_layout
from ..state.app import AppState
from ..state.user_context import UserContextState


def stat_card(title: str, value: rx.Var | str, subtitle: str = "", color_scheme: str = "gray") -> rx.Component:
    """Statistics card component."""
    return rx.card(
        rx.vstack(
            rx.text(title, size="1", color_scheme="gray"),
            rx.heading(value, size="5"),
            rx.cond(
                subtitle != "",
                rx.text(subtitle, size="1", color_scheme=color_scheme),
                rx.fragment(),
            ),
            spacing="1",
            align="start",
        ),
        width="100%",
    )


def quick_action_button(label: str, icon: str, href: str) -> rx.Component:
    """Quick action button component."""
    return rx.link(
        rx.button(
            rx.icon(icon, size=16),
            label,
            variant="outline",
            size="2",
        ),
        href=href,
    )


def dashboard_content() -> rx.Component:
    """Home dashboard content."""
    return rx.vstack(
        # Header
        rx.hstack(
            rx.vstack(
                rx.heading("Welcome back", size="6"),
                rx.text(
                    rx.text("Profile: ", as_="span"),
                    rx.text(UserContextState.profile_display_name, weight="bold", as_="span"),
                    size="2",
                    color_scheme="gray",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.badge(
                rx.hstack(
                    rx.icon("activity", size=14),
                    rx.text("Markets Open", size="1"),
                    spacing="1",
                ),
                color_scheme="green",
                variant="soft",
            ),
            width="100%",
            align="center",
        ),
        rx.divider(),
        # Stats row
        rx.grid(
            stat_card("Watchlist", UserContextState.watchlist_count, "stocks tracked"),
            stat_card("Open Positions", "0", "coming soon"),
            stat_card("This Week", "--", "P&L"),
            stat_card("Win Rate", "--", "coming soon"),
            columns="4",
            spacing="4",
            width="100%",
        ),
        rx.divider(),
        # Quick actions
        rx.vstack(
            rx.heading("Quick Actions", size="4"),
            rx.hstack(
                quick_action_button("Research Stock", "search", "/research"),
                quick_action_button("Analyze Note", "file-text", "/notes"),
                quick_action_button("View Options", "bar-chart-2", "/options"),
                quick_action_button("Portfolio", "pie-chart", "/portfolio"),
                spacing="3",
                wrap="wrap",
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        rx.divider(),
        # Getting started section
        rx.vstack(
            rx.heading("Getting Started", size="4"),
            rx.callout(
                rx.vstack(
                    rx.text(
                        "Talk to the assistant on the right to research stocks, "
                        "manage your watchlist, and get trading insights.",
                        size="2",
                    ),
                    rx.text(
                        "Try asking: 'What do you think about NVDA?' or 'Add AAPL to my watchlist'",
                        size="1",
                        color_scheme="gray",
                    ),
                    spacing="2",
                ),
                icon="message-circle",
                color_scheme="blue",
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        spacing="5",
        width="100%",
        align="start",
    )


@rx.page(route="/", title="Home | Phinan Finance Suite", on_load=AppState.set_page("home"))
def index() -> rx.Component:
    """Home page."""
    return main_layout(dashboard_content())
