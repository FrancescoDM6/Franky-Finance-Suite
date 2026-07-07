"""Performance dashboard for the options trade log."""

import reflex as rx

from ..state import OptionsTradingState


def _stat(label: str, value, color=None) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="var(--pfs-text-muted)"),
        rx.text(value, size="5", weight="bold", color=color),
        spacing="1",
        align="start",
    )


def _breakdown_table(title: str, rows) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="1", weight="bold", color="var(--pfs-text-muted)"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell(""),
                    rx.table.column_header_cell("Trades"),
                    rx.table.column_header_cell("Win rate"),
                    rx.table.column_header_cell("Total P/L"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    rows,
                    lambda row: rx.table.row(
                        rx.table.row_header_cell(
                            rx.text(row["label"], size="2", weight="medium"),
                        ),
                        rx.table.cell(row["count"]),
                        rx.table.cell(row["win_rate"]),
                        rx.table.cell(
                            rx.text(
                                row["total_pnl"],
                                color=row["pnl_color"],
                                weight="medium",
                            ),
                        ),
                    ),
                ),
            ),
            width="100%",
            size="1",
        ),
        spacing="1",
        width="100%",
    )


def performance_card() -> rx.Component:
    """Headline stats + per-strategy and per-underlying breakdowns."""
    return rx.cond(
        OptionsTradingState.has_performance,
        rx.vstack(
            rx.grid(
                _stat("Win Rate", OptionsTradingState.fmt_win_rate),
                _stat("Record", OptionsTradingState.fmt_record),
                _stat("Avg Win", OptionsTradingState.fmt_avg_win),
                _stat("Avg Loss", OptionsTradingState.fmt_avg_loss),
                _stat("Expectancy", OptionsTradingState.fmt_expectancy),
                _stat(
                    "Total P/L",
                    OptionsTradingState.fmt_total_pnl,
                    color=OptionsTradingState.total_pnl_color,
                ),
                columns=rx.breakpoints(initial="2", sm="3", md="6"),
                spacing="4",
                width="100%",
            ),
            rx.text(
                "Avg holding period: ",
                OptionsTradingState.fmt_avg_holding,
                ". Expectancy = avg win x win rate - avg loss x loss rate; "
                "scratch trades (P/L $0) count as losses.",
                size="1",
                color="var(--pfs-text-muted)",
            ),
            rx.divider(),
            rx.flex(
                rx.box(
                    _breakdown_table(
                        "BY STRATEGY", OptionsTradingState.by_strategy_rows
                    ),
                    flex="1",
                    min_width="0",
                ),
                rx.box(
                    _breakdown_table(
                        "BY UNDERLYING", OptionsTradingState.by_underlying_rows
                    ),
                    flex="1",
                    min_width="0",
                ),
                direction=rx.breakpoints(initial="column", md="row"),
                gap="16px",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        rx.center(
            rx.text(
                "Performance metrics appear once you close trades.",
                size="2",
                color="var(--pfs-text-muted)",
            ),
            padding="32px",
            width="100%",
        ),
    )
