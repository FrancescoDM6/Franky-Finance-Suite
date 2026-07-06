"""Monte Carlo outcome distribution chart for the Notes module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import NotesState


def mc_chart() -> rx.Component:
    """Histogram of simulated total returns at redemption."""
    return content_card(
        rx.vstack(
            card_header(
                "Outcome Distribution",
                rx.badge(
                    NotesState.simulation.get("n_paths").to(str),
                    " paths",
                    variant="soft",
                ),
                icon="chart-column",
            ),
            rx.recharts.bar_chart(
                rx.recharts.bar(
                    data_key="pct",
                    fill="var(--accent-9)",
                    radius=[2, 2, 0, 0],
                ),
                rx.recharts.x_axis(
                    data_key="label",
                    tick_line=False,
                    axis_line=False,
                    interval="preserveStartEnd",
                    custom_attrs={"fontSize": "11px"},
                ),
                rx.recharts.y_axis(
                    tick_line=False,
                    axis_line=False,
                    unit="%",
                    custom_attrs={"fontSize": "11px"},
                ),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", opacity=0.3),
                rx.recharts.graphing_tooltip(),
                data=NotesState.outcome_histogram,
                width="100%",
                height=260,
            ),
            rx.text(
                "Total return per simulated path, held to redemption "
                "(coupons + principal). Tail beyond the 1st/99th percentile "
                "is clipped into the edge buckets.",
                size="1",
                color="var(--pfs-text-muted)",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
