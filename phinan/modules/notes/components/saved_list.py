"""Saved note analyses list for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState


def _saved_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(row["label"], size="2", weight="medium"),
            rx.text(row["created_at"], size="1", color="var(--pfs-text-muted)"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.badge(row["fee"], " fee", variant="soft", size="1"),
        rx.button(
            "Load",
            on_click=lambda: NotesState.load_saved(row["id"]),
            variant="soft",
            size="1",
        ),
        rx.alert_dialog.root(
            rx.alert_dialog.trigger(
                rx.button(
                    rx.icon("trash-2", size=14),
                    variant="ghost",
                    color_scheme="gray",
                    size="1",
                ),
            ),
            rx.alert_dialog.content(
                rx.alert_dialog.title("Delete saved analysis"),
                rx.alert_dialog.description(
                    rx.text("Delete '", row["label"], "'? This cannot be undone."),
                ),
                rx.flex(
                    rx.alert_dialog.cancel(
                        rx.button("Cancel", variant="soft", color_scheme="gray"),
                    ),
                    rx.alert_dialog.action(
                        rx.button(
                            "Delete",
                            color_scheme="red",
                            on_click=lambda: NotesState.delete_saved(row["id"]),
                        ),
                    ),
                    spacing="3",
                    justify="end",
                    margin_top="12px",
                ),
                max_width="380px",
            ),
        ),
        width="100%",
        align="center",
        padding="6px",
        class_name="shark-hover",
        border_radius="6px",
    )


def saved_list() -> rx.Component:
    """Recent analyses, loadable with one click."""
    return rx.cond(
        NotesState.has_saved,
        content_card(
            rx.vstack(
                card_header(
                    "Saved Analyses",
                    rx.badge(
                        NotesState.saved_analyses.length(), variant="soft", size="1"
                    ),
                    icon="folder-open",
                ),
                rx.foreach(NotesState.saved_rows, _saved_row),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )
