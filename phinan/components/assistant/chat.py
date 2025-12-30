"""Chat interface component for the assistant."""

import reflex as rx

from .state import AssistantState
from ...state.app import AppState


def message_bubble(message: dict) -> rx.Component:
    """Single chat message bubble."""
    is_user = message.get("role") == "user"

    return rx.box(
        rx.markdown(
            message.get("content", ""),
            component_map={
                "p": lambda text: rx.text(text, size="2"),
                "strong": lambda text: rx.text(text, weight="bold", size="2"),
            },
        ),
        background=rx.cond(
            is_user,
            "var(--accent-a4)",
            "var(--gray-a3)",
        ),
        padding="12px",
        border_radius="12px",
        max_width="85%",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
    )


def chat_messages() -> rx.Component:
    """Scrollable chat messages container."""
    return rx.box(
        rx.vstack(
            rx.cond(
                AssistantState.has_messages,
                rx.foreach(AssistantState.messages, message_bubble),
                rx.center(
                    rx.vstack(
                        rx.icon("message-circle", size=32, color="var(--gray-8)"),
                        rx.text("Start a conversation", color_scheme="gray", size="2"),
                        rx.text(
                            "Ask about stocks, strategies, or your watchlist",
                            color_scheme="gray",
                            size="1",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    height="100%",
                    width="100%",
                ),
            ),
            rx.cond(
                AssistantState.is_thinking,
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Thinking...", size="1", color_scheme="gray"),
                    spacing="2",
                    padding="8px",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
            height="100%",
            align="stretch",
        ),
        flex="1",
        overflow_y="auto",
        padding="12px",
        width="100%",
    )


def chat_input() -> rx.Component:
    """Chat input area with send button."""
    return rx.hstack(
        rx.input(
            placeholder="Ask about stocks, strategies...",
            value=AssistantState.current_input,
            on_change=AssistantState.set_input,
            on_key_down=AssistantState.handle_key_down,
            flex="1",
            size="2",
        ),
        rx.button(
            rx.icon("send", size=16),
            on_click=AssistantState.send_message,
            loading=AssistantState.is_thinking,
            disabled=AssistantState.is_thinking,
            color_scheme="blue",
            size="2",
        ),
        spacing="2",
        padding="12px",
        width="100%",
        border_top="1px solid var(--gray-a5)",
        background="var(--color-background)",
    )


def assistant_header() -> rx.Component:
    """Assistant panel header."""
    return rx.hstack(
        rx.hstack(
            rx.icon("bot", size=18, color="var(--accent-9)"),
            rx.heading("Phin", size="3"),
            spacing="2",
            align="center",
        ),
        rx.spacer(),
        rx.hstack(
            rx.tooltip(
                rx.button(
                    rx.icon("plus", size=14),
                    on_click=AssistantState.new_conversation,
                    variant="ghost",
                    size="1",
                ),
                content="New conversation",
            ),
            rx.tooltip(
                rx.button(
                    rx.icon("trash-2", size=14),
                    on_click=AssistantState.clear_chat,
                    variant="ghost",
                    size="1",
                    color_scheme="red",
                ),
                content="Clear chat",
            ),
            rx.tooltip(
                rx.icon_button(
                    rx.icon("x", size=16),
                    on_click=AppState.toggle_assistant,
                    variant="ghost",
                    size="1",
                    color_scheme="gray",
                ),
                content="Close",
            ),
            spacing="1",
        ),
        width="100%",
        padding="12px",
        border_bottom="1px solid var(--gray-a5)",
        background="var(--color-background)",
    )


def assistant_panel() -> rx.Component:
    """Complete assistant chat panel (floating detached window)."""
    return rx.box(
        rx.vstack(
            assistant_header(),
            chat_messages(),
            chat_input(),
            spacing="0",
            height="100%",
            width="100%",
        ),
        width="350px",
        height="500px",
        border="1px solid var(--gray-a5)",
        border_radius="12px",
        background="var(--color-background)",
        position="fixed",
        right="20px",
        bottom="80px",  # Floating above the FAB/Bottom Area
        display="flex",
        flex_direction="column",
        z_index="50",
        box_shadow="var(--shadow-5)",
    )
