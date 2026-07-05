"""News card component."""

import reflex as rx
from ....components.ui import card_header
from ..state import ResearchState


def sentiment_badge_with_confidence(item) -> rx.Component:
    """Sentiment badge with confidence percentage."""
    return rx.hstack(
        rx.match(
            item.sentiment_label,
            ("positive", rx.badge("Positive", color_scheme="green", size="1")),
            ("negative", rx.badge("Negative", color_scheme="red", size="1")),
            rx.badge("Neutral", color_scheme="gray", size="1"),
        ),
        rx.text(
            item.sentiment_score_fmt,
            size="1",
            color_scheme="gray",
        ),
        spacing="1",
        align="center",
    )


def aggregate_sentiment_header() -> rx.Component:
    """Header showing aggregate sentiment across all news."""
    return rx.cond(
        ResearchState.sentiment_total > 0,
        rx.vstack(
            rx.hstack(
                rx.text("Overall: ", size="2", weight="medium"),
                rx.match(
                    ResearchState.aggregate_sentiment.get("dominant"),
                    ("positive", rx.badge("Positive", color_scheme="green", size="2")),
                    ("negative", rx.badge("Negative", color_scheme="red", size="2")),
                    rx.badge("Neutral", color_scheme="gray", size="2"),
                ),
                rx.text(
                    "(",
                    ResearchState.sentiment_confidence_pct,
                    "%)",
                    size="2",
                    color_scheme="gray",
                ),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.hstack(
                    rx.box(width="12px", height="12px", background="var(--green-9)", border_radius="2px"),
                    rx.text(ResearchState.sentiment_positive_count, size="1"),
                    spacing="1",
                    align="center",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="var(--gray-9)", border_radius="2px"),
                    rx.text(ResearchState.sentiment_neutral_count, size="1"),
                    spacing="1",
                    align="center",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="var(--red-9)", border_radius="2px"),
                    rx.text(ResearchState.sentiment_negative_count, size="1"),
                    spacing="1",
                    align="center",
                ),
                spacing="3",
            ),
            spacing="2",
            width="100%",
            padding_bottom="2",
        ),
        rx.fragment(),
    )


def news_card() -> rx.Component:
    """Recent news card with sentiment analysis."""
    return rx.card(
        rx.vstack(
            card_header(
                "Recent News",
                rx.badge(
                    ResearchState.recent_news.length(),
                    variant="soft",
                ),
            ),
            aggregate_sentiment_header(),
            rx.cond(
                ResearchState.recent_news.length() > 0,
                rx.vstack(
                    rx.foreach(
                        ResearchState.recent_news,
                        lambda item: rx.hstack(
                            rx.icon("newspaper", size=14, color="var(--gray-9)"),
                            rx.vstack(
                                rx.hstack(
                                    rx.cond(
                                        item.link != "",
                                        rx.link(
                                            item.title,
                                            href=item.link,
                                            is_external=True,
                                            size="2",
                                            weight="medium",
                                        ),
                                        rx.text(item.title, size="2", weight="medium", as_="span"),
                                    ),
                                    sentiment_badge_with_confidence(item),
                                    spacing="2",
                                    align="center",
                                    wrap="wrap",
                                ),
                                rx.text(item.publisher, size="1", color_scheme="gray", as_="span"),
                                spacing="0",
                                align="start",
                            ),
                            spacing="2",
                            width="100%",
                            padding_y="2",
                        ),
                    ),
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
