"""Sidebar navigation component."""

import reflex as rx

from ..state.app import AppState
from ..state.user_context import UserContextState


def nav_item(label: str, icon: str, route: str, page_id: str) -> rx.Component:
    """Single navigation item."""
    # Use router path directly for active state detection
    # For home ("/"), exact match; for others, check if path starts with route
    current_path = rx.State.router.page.path
    is_active = rx.cond(
        route == "/",
        current_path == "/",
        current_path.contains(route),
    )

    return rx.link(
        rx.hstack(
            rx.icon(icon, size=18),
            rx.text(label, size="2"),
            spacing="3",
            width="100%",
            padding="2",
            border_radius="md",
            background=rx.cond(is_active, "var(--accent-a4)", "transparent"),
            color=rx.cond(is_active, "var(--accent-11)", "var(--gray-11)"),
            class_name="shark-hover",
        ),
        href=route,
        width="100%",
        underline="none",
    )


def watchlist_section() -> rx.Component:
    """Watchlist display in sidebar."""
    from ..modules.research.state import ResearchState

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("Watchlist", size="1", weight="bold", color_scheme="gray", padding="8px"),
                rx.spacer(),
                rx.badge(
                    UserContextState.watchlist_count,
                    variant="soft",
                    size="1",
                ),
                width="100%",
            ),
            rx.cond(
                UserContextState.watchlist_count > 0,
                rx.vstack(
                    rx.foreach(
                        UserContextState.watchlist,
                        lambda symbol: rx.hstack(
                            rx.text(
                                symbol, 
                                size="1", 
                                weight="medium",
                                cursor="pointer",
                                _hover={"color": "var(--accent-9)"},
                                on_click=lambda: ResearchState.search_ticker(symbol),
                            ),
                            rx.spacer(),
                            rx.button(
                                rx.icon("x", size=12),
                                on_click=lambda: UserContextState.remove_from_watchlist(symbol),
                                variant="ghost",
                                size="1",
                                color_scheme="gray",
                            ),
                            width="100%",
                            padding="4px",
                            class_name="shark-hover",
                            border_radius="4px",
                        ),
                    ),
                    spacing="1",
                    width="100%",
                    
                ),
                
                rx.text("No stocks in watchlist", size="1", color_scheme="gray", padding="8px" ),
            ),
            spacing="2",
            width="100%",
        ),
        padding="3px",
        border_top="1px solid var(--gray-a5)",
    )


def positions_section() -> rx.Component:
    """Portfolio positions display in sidebar."""
    # Import here to avoid circular import
    from ..modules.portfolio.state import PortfolioState
    from ..modules.research.state import ResearchState
    
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text("Positions", size="1", weight="bold", color_scheme="gray", padding="8px"),
                rx.spacer(),
                rx.badge(
                    PortfolioState.positions.length(),
                    variant="soft",
                    size="1",
                    color_scheme="green",
                ),
                width="100%",
            ),
            rx.cond(
                PortfolioState.has_positions,
                rx.vstack(
                    rx.foreach(
                        PortfolioState.positions,
                        lambda pos: rx.hstack(
                            rx.text(
                                pos.ticker_symbol, 
                                size="1", 
                                weight="medium",
                                cursor="pointer",
                                _hover={"color": "var(--accent-9)"},
                                on_click=lambda: ResearchState.search_ticker(pos.ticker_symbol),
                            ),
                            rx.spacer(),
                            rx.text(
                                rx.cond(
                                    pos.gain_loss_percent >= 0,
                                    f"+{pos.gain_loss_percent:.1f}%",
                                    f"{pos.gain_loss_percent:.1f}%",
                                ),
                                size="1",
                                color=rx.cond(
                                    pos.gain_loss_percent >= 0,
                                    "var(--green-11)",
                                    "var(--red-11)",
                                ),
                            ),
                            width="100%",
                            padding="4px",
                            class_name="shark-hover",
                            border_radius="4px",
                        ),
                    ),
                    spacing="1",
                    width="100%",
                ),
                rx.text("No positions yet", size="1", color_scheme="gray", padding="8px"),
            ),
            spacing="2",
            width="100%",
        ),
        padding="3px",
        border_top="1px solid var(--gray-a5)",
    )


def sidebar_footer() -> rx.Component:
    """Sidebar footer with user controls."""
    return rx.vstack(
        rx.divider(),
        # Profile Selector
        rx.box(
            rx.text("Profile", size="1", weight="bold", color_scheme="gray", margin_bottom="4px"),
            rx.select(
                ["Conservative", "Aggressive", "Standard"],
                value=UserContextState.profile_display_name,
                on_change=UserContextState.set_profile,
                placeholder="Profile",
                size="2",
                width="100%",
            ),
            width="100%",
        ),
        # Action Buttons
        rx.hstack(
            rx.tooltip(
                rx.icon_button(
                    rx.cond(
                        rx.color_mode == "dark",
                        rx.icon("sun", size=18),
                        rx.icon("moon", size=18),
                    ),
                    on_click=rx.toggle_color_mode,
                    variant="soft",
                    color_scheme="gray",
                    size="2",
                    flex="1",
                    width="100%",
                    class_name="shark-hover",
                ),
                content="Toggle Theme",
            ),
            rx.tooltip(
                rx.icon_button(
                    rx.icon("settings", size=18),
                    on_click=rx.redirect("/settings"),
                    variant="soft",
                    color_scheme="gray",
                    size="2",
                    flex="1",
                    width="100%",
                    class_name="shark-hover",
                ),
                content="Settings",
            ),
            spacing="2",
            width="100%",
        ),
        spacing="4",
        width="100%",
        padding="16px",
        background="var(--gray-a2)",
    )


def sidebar() -> rx.Component:
    """Application sidebar with navigation."""
    return rx.flex(
        rx.vstack(
            # Logo area
            rx.box(
                rx.hstack(
                    # Custom Shark Fin Icon (Detached Chevron)
                    rx.html(
                        """
                        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--accent-9)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <!-- Fin Body (Stops short of the tip) -->
                            <path d="M 4 20 C 10 18 16 11 19 6 Q 23 13 20 20" />
                            <!-- Detached Chevron (Floating Tip) -->
                            <!-- Left leg aligns with back curve, Right leg aligns with front curve -->
                            <polyline points="16 3 22 3 23 8" />
                        </svg>
                        """
                    ),
                    rx.heading("Phinan", size="7", color="var(--accent-11)"),
                    spacing="2",
                    align="center",
                ),
                padding="20px",
                background="linear-gradient(180deg, var(--gray-a2) 0%, transparent 100%)",
            ),
            # Navigation items
            rx.vstack(
                nav_item("Home", "home", "/", "home"),
                nav_item("Research", "search", "/research", "research"),
                nav_item("Notes", "file-text", "/notes", "notes"),
                nav_item("Options", "bar-chart-2", "/options", "options"),
                nav_item("Portfolio", "pie-chart", "/portfolio", "portfolio"),
                spacing="1",
                width="100%",
                padding_x="12px",
            ),
            # Watchlist section
            rx.box(
                watchlist_section(),
                padding_x="3",
                width="100%",
            ),
            # Positions section
            rx.box(
                positions_section(),
                padding_x="3",
                width="100%",
            ),
            spacing="4",
            width="100%",
            flex="1",  # Push footer down
            overflow_y="auto",
        ),
        sidebar_footer(),
        direction="column",
        width="240px",
        height="100vh",
        border_right="1px solid var(--gray-a5)",
        class_name="sidebar-depth",
        z_index="50",
    )
