"""Main application layout with sidebar and assistant panel."""

import reflex as rx

from ..state.app import AppState
from .sidebar import sidebar


def main_layout(*children) -> rx.Component:
    """Main application layout wrapper.
    
    Architecture:
    - Root: Flex container (row)
    - Sidebar: Fixed width (flex-none)
    - Content: Flexible width (flex-1), scrollable
    - Assistant: Floating overlay (absolute)
    """
    return rx.box(
        # Mobile top bar
        rx.hstack(
            rx.icon_button(
                rx.icon("menu", size=20),
                on_click=AppState.toggle_sidebar,
                variant="soft",
                color_scheme="gray",
                size="2",
            ),
            rx.heading("Phinan", size="5", color="var(--accent-11)"),
            width="100%",
            height="56px",
            padding_x="12px",
            border_bottom="1px solid var(--gray-a5)",
            background="var(--color-background)",
            align="center",
            spacing="3",
            display=rx.breakpoints(initial="flex", sm="none"),
            flex_shrink="0",
        ),

        # Mobile sidebar overlay
        rx.cond(
            AppState.sidebar_open,
            rx.box(
                sidebar(),
                position="fixed",
                top="0",
                left="0",
                width="100%",
                height="100vh",
                z_index="100",
                background="var(--color-background)",
                display=rx.breakpoints(initial="block", sm="none"),
            ),
            rx.fragment(),
        ),

        # Desktop sidebar, always inline.
        rx.box(
            sidebar(),
            display=rx.breakpoints(initial="none", sm="block"),
            flex_shrink="0",
        ),

        # Main content area
        rx.box(
            *children,
            flex="1",
            min_height="0",
            min_width="0",
            padding=rx.breakpoints(initial="12px", sm="24px"),
            overflow_y="auto",
            width="100%",
        ),

        # Use rx.box + flex_direction (CSS) instead of rx.flex + direction
        # because Radix's `direction` prop on rx.flex does not respond to
        # rx.breakpoints, leaving the layout as row on mobile and squeezing
        # the main content to zero width.
        display="flex",
        flex_direction=rx.breakpoints(initial="column", sm="row"),
        width="100%",
        height="100vh",
        background="var(--pfs-bg)",
        color="var(--pfs-text)",
        overflow="hidden",  # Prevent window scroll
    )
