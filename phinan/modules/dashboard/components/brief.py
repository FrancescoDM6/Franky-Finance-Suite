"""Daily brief presentation components."""

import reflex as rx

from ....components.ui import synthesis_card
from ..state import DailyBriefState


def daily_brief_card() -> rx.Component:
    """Render Phin's Daily Brief card."""
    return synthesis_card(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon("sparkles", size=18, color="var(--purple-9)"),
                    rx.heading("Phin's Daily Brief", size="4"),
                    spacing="2",
                    align="center",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.cond(
                        DailyBriefState.brief_generated_at != "",
                        rx.text(
                            DailyBriefState.brief_generated_at,
                            size="1",
                            color_scheme="gray",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        rx.icon("refresh-cw", size=14),
                        on_click=DailyBriefState.force_regenerate_brief,
                        variant="ghost",
                        size="1",
                        loading=DailyBriefState.brief_loading,
                    ),
                    spacing="2",
                    align="center",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            rx.cond(
                DailyBriefState.brief_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="2"),
                        rx.text(
                            DailyBriefState.loading_status,
                            size="1",
                            color_scheme="gray",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    padding="6",
                ),
                rx.cond(
                    DailyBriefState.brief_error != "",
                    rx.callout(
                        DailyBriefState.brief_error,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.cond(
                        DailyBriefState.brief_content != "",
                        rx.markdown(
                            DailyBriefState.safe_brief_content,
                            component_map={
                                "h2": lambda text: rx.heading(
                                    text,
                                    size="4",
                                    margin_top="0.5em",
                                    margin_bottom="0.25em",
                                ),
                                "h3": lambda text: rx.heading(
                                    text,
                                    size="3",
                                    margin_top="0.5em",
                                    margin_bottom="0.25em",
                                ),
                                "p": lambda text: rx.text(
                                    text, size="2", margin_bottom="0.5em"
                                ),
                                "li": lambda text: rx.text(
                                    text,
                                    size="2",
                                    display="list-item",
                                    margin_left="1em",
                                ),
                            },
                        ),
                        rx.center(
                            rx.vstack(
                                rx.icon("sun", size=32, color="var(--amber-9)"),
                                rx.text(
                                    "Click refresh to generate today's brief",
                                    size="2",
                                    color_scheme="gray",
                                ),
                                spacing="2",
                                align="center",
                            ),
                            padding="6",
                        ),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
