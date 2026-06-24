"""Dashboard alert components."""

import reflex as rx

from ....components.ui import content_card
from ..state import DailyBriefState


def news_alerts_card() -> rx.Component:
    """Render compact news alerts for portfolio holdings."""
    return rx.cond(
        DailyBriefState.news_alerts.length() > 0,
        content_card(
            rx.vstack(
                rx.hstack(
                    rx.icon("bell", size=16, color="var(--amber-9)"),
                    rx.heading("News Alerts", size="4"),
                    rx.spacer(),
                    rx.badge(
                        DailyBriefState.news_alerts.length(),
                        variant="soft",
                        size="1",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.divider(),
                rx.foreach(
                    DailyBriefState.news_alerts[:5],
                    lambda item: rx.hstack(
                        rx.badge(item["ticker"], size="1", variant="soft"),
                        rx.link(
                            rx.text(
                                item["title"],
                                size="1",
                                style={
                                    "text_overflow": "ellipsis",
                                    "overflow": "hidden",
                                    "white_space": "nowrap",
                                },
                            ),
                            href=item["link"],
                            is_external=True,
                            style={"flex": "1", "min_width": "0"},
                        ),
                        spacing="2",
                        width="100%",
                        align="center",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )
