"""Main application layout with sidebar and assistant panel."""

import reflex as rx

from ..state.app import AppState
from .sidebar import sidebar
from .assistant.chat import assistant_panel


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
        
        # Floating Action Button for Assistant
        rx.tooltip(
            rx.icon_button(
                rx.icon("message-circle", size=24),
                on_click=AppState.toggle_assistant,
                variant="solid",
                color_scheme="blue",
                size="4",
                radius="full",
                position="fixed",
                bottom="32px",
                right="32px",
                z_index="40",
                box_shadow="var(--shadow-4)",
            ),
            content="Chat with Phinan",
        ),

        # Assistant panel (Floating Overlay)
        rx.cond(
            AppState.assistant_visible,
            assistant_panel(),
            rx.fragment(),
        ),
        
        width="100%",
        height="100vh",
        background="var(--gray-a2)",
        overflow="hidden",  # Prevent window scroll
    )
