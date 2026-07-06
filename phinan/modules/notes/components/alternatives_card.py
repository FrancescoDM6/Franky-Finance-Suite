"""Alternatives comparison table for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState


def _row(row: dict) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.vstack(
                rx.text(row["strategy"], size="2", weight="medium"),
                rx.text(row["caveat"], size="1", color="var(--pfs-text-muted)"),
                spacing="0",
                align="start",
            ),
        ),
        rx.table.cell(row["expected_irr"]),
        rx.table.cell(row["median"]),
        rx.table.cell(row["p5"]),
        rx.table.cell(row["max_loss"]),
    )


def alternatives_card() -> rx.Component:
    """Same money, same horizon: the note vs simple alternatives."""
    return content_card(
        rx.vstack(
            card_header("vs. Alternatives", icon="git-compare"),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Strategy"),
                        rx.table.column_header_cell("Expected (ann.)"),
                        rx.table.column_header_cell("Median total"),
                        rx.table.column_header_cell("Bottom 5%"),
                        rx.table.column_header_cell("Max loss"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(NotesState.alternative_rows, _row),
                ),
                width="100%",
                size="1",
            ),
            rx.text(
                "Equity-based rows are evaluated on the same simulated "
                "worst-of paths as the note.",
                size="1",
                color="var(--pfs-text-muted)",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
