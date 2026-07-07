"""Options chain viewer for the trading page.

Dense strike window centered on ATM; clicking a row prefills the trade
form and strategy preview.
"""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import OptionsTradingState


def _ticker_input() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.input(
                value=OptionsTradingState.form_chain_ticker,
                on_change=OptionsTradingState.set_chain_ticker_input,
                placeholder="Ticker (e.g. AAPL)",
                size="2",
                width="160px",
            ),
            rx.button(
                rx.icon("search", size=16),
                "Load Chain",
                on_click=OptionsTradingState.load_chain_for_ticker,
                loading=OptionsTradingState.chain_loading,
                size="2",
            ),
            spacing="2",
            align="center",
        ),
        rx.cond(
            OptionsTradingState.show_autocomplete
            & (OptionsTradingState.ticker_suggestions.length() > 0),
            rx.box(
                rx.foreach(
                    OptionsTradingState.ticker_suggestions,
                    lambda option: rx.box(
                        rx.text(option, size="1"),
                        on_click=lambda: OptionsTradingState.select_ticker_suggestion(
                            option
                        ),
                        padding="6px 10px",
                        cursor="pointer",
                        class_name="shark-hover",
                    ),
                ),
                position="absolute",
                top="40px",
                left="0",
                background="var(--pfs-surface)",
                border="1px solid var(--gray-a5)",
                border_radius="8px",
                box_shadow="0 4px 12px rgba(0,0,0,0.12)",
                z_index="30",
                width="240px",
                max_height="240px",
                overflow_y="auto",
            ),
            rx.fragment(),
        ),
        position="relative",
    )


def _chain_row(row: dict, option_type: str) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.hstack(
                rx.text(row["strike"], weight="medium", size="2"),
                rx.cond(
                    row["is_atm"],
                    rx.badge("ATM", color_scheme="blue", size="1", variant="soft"),
                    rx.fragment(),
                ),
                spacing="2",
                align="center",
            ),
        ),
        rx.table.cell(row["bid"]),
        rx.table.cell(row["ask"]),
        rx.table.cell(row["mid"]),
        rx.table.cell(row["oi"]),
        rx.table.cell(row["iv_pct"]),
        on_click=lambda: OptionsTradingState.select_chain_row(row, option_type),
        cursor="pointer",
        background=rx.cond(row["is_atm"], "var(--accent-a3)", "transparent"),
        class_name="shark-hover",
    )


def _chain_table(title: str, color: str, rows, option_type: str) -> rx.Component:
    return rx.vstack(
        rx.text(title, size="1", weight="bold", color=color),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Strike"),
                    rx.table.column_header_cell("Bid"),
                    rx.table.column_header_cell("Ask"),
                    rx.table.column_header_cell("Mid"),
                    rx.table.column_header_cell("OI"),
                    rx.table.column_header_cell("IV"),
                ),
            ),
            rx.table.body(
                rx.foreach(rows, lambda row: _chain_row(row, option_type)),
            ),
            width="100%",
            size="1",
        ),
        spacing="1",
        width="100%",
    )


def chain_card() -> rx.Component:
    """Chain viewer: ticker + expiration controls, calls/puts tables."""
    return content_card(
        rx.vstack(
            card_header(
                "Options Chain",
                rx.cond(
                    OptionsTradingState.chain_spot > 0,
                    rx.badge(
                        OptionsTradingState.chain_ticker,
                        " ",
                        OptionsTradingState.chain_spot_label,
                        variant="soft",
                    ),
                    rx.fragment(),
                ),
                icon="table-2",
            ),
            rx.hstack(
                _ticker_input(),
                rx.spacer(),
                rx.cond(
                    OptionsTradingState.chain_expirations.length() > 0,
                    rx.select(
                        OptionsTradingState.chain_expirations,
                        value=OptionsTradingState.chain_expiration,
                        on_change=OptionsTradingState.set_chain_expiration,
                        size="2",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    OptionsTradingState.chain_days_to_expiry > 0,
                    rx.badge(
                        OptionsTradingState.chain_days_to_expiry,
                        "d to expiry",
                        variant="soft",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                width="100%",
                align="center",
                wrap="wrap",
            ),
            rx.cond(
                OptionsTradingState.chain_error != "",
                rx.callout(
                    OptionsTradingState.chain_error,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.cond(
                OptionsTradingState.has_chain_data,
                rx.vstack(
                    rx.flex(
                        rx.box(
                            _chain_table(
                                "CALLS",
                                "var(--green-11)",
                                OptionsTradingState.chain_calls,
                                "call",
                            ),
                            flex="1",
                            min_width="0",
                        ),
                        rx.box(
                            _chain_table(
                                "PUTS",
                                "var(--red-11)",
                                OptionsTradingState.chain_puts,
                                "put",
                            ),
                            flex="1",
                            min_width="0",
                        ),
                        direction=rx.breakpoints(initial="column", md="row"),
                        gap="16px",
                        width="100%",
                    ),
                    rx.text(
                        "Click a row to prefill the trade form (premium = mid).",
                        size="1",
                        color="var(--pfs-text-muted)",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.cond(
                    OptionsTradingState.chain_loading,
                    rx.center(rx.spinner(size="2"), padding="24px", width="100%"),
                    rx.center(
                        rx.text(
                            "Load a ticker to view its options chain.",
                            size="2",
                            color="var(--pfs-text-muted)",
                        ),
                        padding="24px",
                        width="100%",
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
