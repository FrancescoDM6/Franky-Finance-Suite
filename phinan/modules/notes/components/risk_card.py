"""Risk scenarios card for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState


def _prob(label: str, value, color=None) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="var(--pfs-text-muted)"),
        rx.text(value, size="4", weight="bold", color=color),
        spacing="1",
        align="start",
    )


def risk_card() -> rx.Component:
    """Probabilities and outcome percentiles."""
    return content_card(
        rx.vstack(
            card_header(
                "Risk Scenarios",
                rx.badge(
                    "Expected life ", NotesState.fmt_expected_life, variant="soft"
                ),
                icon="shield-alert",
            ),
            rx.grid(
                _prob("P(Autocalled early)", NotesState.fmt_prob_autocall),
                _prob("P(Barrier breached)", NotesState.fmt_prob_breach),
                _prob(
                    "P(You lose money)",
                    NotesState.fmt_prob_loss,
                    color=rx.match(
                        NotesState.prob_loss_color,
                        ("green", "var(--green-11)"),
                        ("amber", "var(--amber-11)"),
                        ("red", "var(--red-11)"),
                        "var(--gray-11)",
                    ),
                ),
                _prob("Median return (ann.)", NotesState.fmt_median_irr),
                columns=rx.breakpoints(initial="2", sm="4"),
                spacing="4",
                width="100%",
            ),
            rx.divider(),
            rx.vstack(
                rx.text(
                    "Total return by scenario",
                    size="1",
                    weight="medium",
                    color="var(--pfs-text-muted)",
                ),
                rx.foreach(
                    NotesState.percentile_rows,
                    lambda row: rx.hstack(
                        rx.text(row["label"], size="2"),
                        rx.spacer(),
                        rx.text(row["value"], size="2", weight="medium"),
                        width="100%",
                    ),
                ),
                spacing="1",
                width="100%",
            ),
            rx.cond(
                NotesState.has_timeline,
                rx.vstack(
                    rx.divider(),
                    rx.text(
                        "Autocall timeline (chance of early redemption)",
                        size="1",
                        weight="medium",
                        color="var(--pfs-text-muted)",
                    ),
                    rx.foreach(
                        NotesState.timeline_rows,
                        lambda row: rx.hstack(
                            rx.text(row["date"], size="2"),
                            rx.spacer(),
                            rx.text(row["probability"], size="2"),
                            rx.text(
                                "(cum. ",
                                row["cumulative"],
                                ")",
                                size="1",
                                color="var(--pfs-text-muted)",
                            ),
                            width="100%",
                            align="center",
                        ),
                    ),
                    spacing="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
