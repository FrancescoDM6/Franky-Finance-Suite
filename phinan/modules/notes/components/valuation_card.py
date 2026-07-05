"""Fee breakdown / valuation card for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState


def _metric(label: str, value, color=None) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="var(--pfs-text-muted)"),
        rx.text(value, size="5", weight="bold", color=color),
        spacing="1",
        align="start",
    )


def valuation_card() -> rx.Component:
    """What the note is worth vs what you pay for it."""
    return content_card(
        rx.vstack(
            card_header(
                "Fee Breakdown",
                rx.badge(
                    NotesState.fmt_implied_fee,
                    " embedded fee",
                    color_scheme=NotesState.implied_fee_color,
                    variant="soft",
                ),
                icon="scale",
            ),
            rx.grid(
                _metric("Fair Value", NotesState.fmt_fair_value),
                _metric("Bond Floor", NotesState.fmt_bond_floor),
                _metric("Coupon / Option Value", NotesState.fmt_option_value),
                _metric("Expected Return (ann.)", NotesState.fmt_expected_irr),
                columns=rx.breakpoints(initial="2", sm="4"),
                spacing="4",
                width="100%",
            ),
            rx.text(
                "You pay 100%. Fair value is the simulated worth of what "
                "you receive; the difference is the issuer's margin.",
                size="1",
                color="var(--pfs-text-muted)",
            ),
            rx.text(
                NotesState.audit_footnote,
                size="1",
                color="var(--pfs-text-muted)",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
