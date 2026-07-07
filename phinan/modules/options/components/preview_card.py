"""Single-leg strategy preview: metrics grid + payoff diagram."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import OptionsTradingState


def _metric(label: str, value) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="var(--pfs-text-muted)"),
        rx.text(value, size="4", weight="bold"),
        spacing="1",
        align="start",
    )


def _payoff_chart() -> rx.Component:
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="pnl",
            stroke="var(--accent-9)",
            stroke_width=2,
            dot=False,
        ),
        rx.recharts.x_axis(
            data_key="price",
            type_="number",
            domain=["dataMin", "dataMax"],
            tick_line=False,
            axis_line=False,
            custom_attrs={"fontSize": "11px"},
        ),
        rx.recharts.y_axis(
            tick_line=False,
            axis_line=False,
            custom_attrs={"fontSize": "11px"},
        ),
        rx.recharts.reference_line(y=0, stroke="var(--gray-8)"),
        rx.recharts.reference_line(
            # ReferenceLine.x only accepts str | int vars
            x=OptionsTradingState.chain_spot.to(int),
            stroke="var(--amber-9)",
            stroke_dasharray="4 4",
        ),
        rx.recharts.cartesian_grid(stroke_dasharray="3 3", opacity=0.3),
        rx.recharts.graphing_tooltip(),
        data=OptionsTradingState.payoff_data,
        width="100%",
        height=240,
    )


def preview_card() -> rx.Component:
    """What the currently entered trade looks like at expiration."""
    return content_card(
        rx.vstack(
            card_header(
                "Strategy Preview",
                rx.cond(
                    OptionsTradingState.has_preview,
                    rx.badge(
                        OptionsTradingState.form_strategy, variant="soft", size="1"
                    ),
                    rx.fragment(),
                ),
                icon="line-chart",
            ),
            rx.cond(
                OptionsTradingState.has_preview,
                rx.vstack(
                    rx.grid(
                        _metric("Entry", OptionsTradingState.fmt_entry),
                        _metric("Break-even", OptionsTradingState.fmt_break_even),
                        _metric("Max Profit", OptionsTradingState.fmt_max_profit),
                        _metric("Max Loss", OptionsTradingState.fmt_max_loss),
                        _metric("Est. PoP", OptionsTradingState.fmt_pop),
                        columns=rx.breakpoints(initial="2", sm="5"),
                        spacing="4",
                        width="100%",
                    ),
                    rx.cond(
                        OptionsTradingState.has_greeks,
                        rx.hstack(
                            rx.foreach(
                                OptionsTradingState.greek_rows,
                                lambda row: rx.badge(
                                    row["label"], " ", row["value"],
                                    variant="soft",
                                    color_scheme="gray",
                                    size="1",
                                ),
                            ),
                            spacing="2",
                            wrap="wrap",
                        ),
                        rx.text(
                            "Greeks and PoP need an IV value - fill the IV field "
                            "or click a chain row.",
                            size="1",
                            color="var(--pfs-text-muted)",
                        ),
                    ),
                    rx.divider(),
                    _payoff_chart(),
                    rx.text(
                        "P/L at expiration vs underlying price (window clipped "
                        "to +/-30% of spot; dashed line = current spot). Est. "
                        "PoP is a risk-neutral lognormal estimate from the "
                        "entered IV.",
                        size="1",
                        color="var(--pfs-text-muted)",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("mouse-pointer-click", size=32, color="var(--gray-8)"),
                        rx.text(
                            "Click a chain row or fill in strike, premium, and "
                            "contracts to preview the trade.",
                            size="2",
                            color="var(--pfs-text-muted)",
                            text_align="center",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    padding="40px",
                    width="100%",
                ),
            ),
            rx.cond(
                OptionsTradingState.preview_error != "",
                rx.callout(
                    OptionsTradingState.preview_error,
                    icon="circle-alert",
                    color_scheme="amber",
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
