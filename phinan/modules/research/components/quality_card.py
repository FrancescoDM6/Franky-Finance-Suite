"""Quality check card component."""

import reflex as rx
from ..state import ResearchState


def metric_row(label: str, value: rx.Var, format_type: str = "default") -> rx.Component:
    """Single metric row."""
    return rx.hstack(
        rx.text(label, size="2", color_scheme="gray"),
        rx.spacer(),
        rx.text(value, size="2", weight="medium"),
        width="100%",
    )


def quality_card() -> rx.Component:
    """Quality check card showing fundamental assessment."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Quality Check", size="4"),
                rx.spacer(),
                rx.badge(
                    ResearchState.quality_overall,
                    color_scheme=rx.cond(
                        ResearchState.quality_overall == "Pass", "green", "yellow"
                    ),
                    variant="soft",
                ),
                width="100%",
            ),
            rx.divider(),
            rx.vstack(
                metric_row("Industry", ResearchState.quality_check.get("industry", "N/A")),
                metric_row(
                    "P/E Ratio",
                    rx.cond(
                        ResearchState.ticker_info.get("pe_ratio"),
                        ResearchState.ticker_info.get("pe_ratio"),
                        "N/A",
                    ),
                ),
                metric_row(
                    "Profit Margin",
                    rx.cond(
                        ResearchState.ticker_info.get("profit_margin"),
                        rx.text(
                            (ResearchState.ticker_info.get("profit_margin", 0).to(float) * 100).to(int),
                            "%",
                        ),
                        "N/A",
                    ),
                ),
                metric_row(
                    "Debt/Equity",
                    rx.cond(
                        ResearchState.ticker_info.get("debt_to_equity"),
                        ResearchState.ticker_info.get("debt_to_equity"),
                        "N/A",
                    ),
                ),
                metric_row(
                    "Dividend Yield",
                    rx.cond(
                        ResearchState.ticker_info.get("dividend_yield"),
                        rx.text(
                            (ResearchState.ticker_info.get("dividend_yield", 0).to(float) * 100).to(int),
                            "%",
                        ),
                        "N/A",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            # Warning flags
            rx.cond(
                ResearchState.quality_flags.length() > 0,
                rx.vstack(
                    rx.divider(),
                    rx.foreach(
                        ResearchState.quality_flags,
                        lambda flag: rx.hstack(
                            rx.icon("triangle-alert", size=14, color="orange"),
                            rx.text(flag, size="1", color_scheme="orange"),
                            spacing="2",
                        ),
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
