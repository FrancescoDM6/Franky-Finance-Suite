"""Term sheet upload zone for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState

UPLOAD_ID = "note_upload"


def upload_card() -> rx.Component:
    """PDF drop zone that extracts terms into the form (no auto-analysis)."""
    return content_card(
        rx.vstack(
            card_header("Term Sheet", icon="file-text"),
            rx.hstack(
                rx.upload(
                    rx.vstack(
                        rx.icon("cloud-upload", size=28, color="var(--accent-9)"),
                        rx.text("Drop a term sheet PDF here", size="2"),
                        rx.text(
                            "AI fills the form; you review before analyzing",
                            size="1",
                            color="var(--pfs-text-muted)",
                        ),
                        rx.foreach(
                            rx.selected_files(UPLOAD_ID),
                            lambda f: rx.badge(f, variant="soft", size="1"),
                        ),
                        spacing="1",
                        align="center",
                    ),
                    id=UPLOAD_ID,
                    multiple=False,
                    accept={"application/pdf": [".pdf"]},
                    max_files=1,
                    border="2px dashed var(--accent-a6)",
                    border_radius="10px",
                    padding="20px",
                    width="100%",
                ),
                rx.vstack(
                    rx.button(
                        rx.icon("sparkles", size=16),
                        "Extract Terms",
                        on_click=NotesState.handle_upload(
                            rx.upload_files(upload_id=UPLOAD_ID)
                        ),
                        loading=NotesState.is_parsing,
                        size="2",
                        width="100%",
                    ),
                    rx.button(
                        "Manual Entry",
                        on_click=NotesState.clear_all,
                        variant="soft",
                        color_scheme="gray",
                        size="2",
                        width="100%",
                    ),
                    spacing="2",
                    width="180px",
                ),
                spacing="4",
                width="100%",
                align="center",
            ),
            rx.cond(
                NotesState.has_parse_warnings,
                rx.callout(
                    rx.vstack(
                        rx.text(
                            "Extracted with warnings - review the form before analyzing:",
                            size="1",
                            weight="medium",
                        ),
                        rx.foreach(
                            NotesState.parse_warnings,
                            lambda w: rx.text("- ", w, size="1"),
                        ),
                        spacing="1",
                        align="start",
                    ),
                    icon="triangle-alert",
                    color_scheme="amber",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.cond(
                NotesState.error_message != "",
                rx.callout(
                    NotesState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
