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
    return rx.flex(
        # Sidebar (always visible)
        rx.cond(
            AppState.sidebar_open,
            sidebar(),
            rx.fragment(),
        ),
        
        # Main content area
        rx.box(
            *children,
            flex="1",
            padding="24px",
            height="100vh",
            overflow_y="auto",
            width="100%",
        ),
        
        width="100%",
        height="100vh",
        background="var(--gray-a2)",
        overflow="hidden",  # Prevent window scroll
    )
