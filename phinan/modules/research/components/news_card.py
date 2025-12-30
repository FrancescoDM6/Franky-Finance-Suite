"""News card component."""

import reflex as rx
from ..state import ResearchState


def news_item(item: dict) -> rx.Component:
    """Single news item."""
    return rx.hstack(
        rx.icon("newspaper", size=14, color="var(--gray-9)"),
        rx.vstack(
            rx.text(item.get("title", ""), size="2", weight="medium"),
            rx.text(item.get("publisher", ""), size="1", color_scheme="gray"),
            spacing="0",
            align="start",
        ),
        spacing="2",
        width="100%",
        padding_y="2",
    )


def news_card() -> rx.Component:
    """Recent news card."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Recent News", size="4"),
                rx.spacer(),
                rx.badge(
                    ResearchState.recent_news.length(),
                    variant="soft",
                ),
                width="100%",
            ),
            rx.divider(),
            rx.cond(
                ResearchState.recent_news.length() > 0,
                rx.vstack(
                    rx.foreach(ResearchState.recent_news, news_item),
                    spacing="1",
                    width="100%",
                ),
                rx.center(
                    rx.text("No recent news", size="2", color_scheme="gray"),
                    padding="4",
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
