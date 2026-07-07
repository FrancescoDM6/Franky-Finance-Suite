"""Open/closed trade tables with close, expire, edit, and delete flows."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..state import OptionsTradingState


def _empty(text: str) -> rx.Component:
    return rx.center(
        rx.text(text, size="2", color="var(--pfs-text-muted)"),
        padding="32px",
        width="100%",
    )


def _open_row(trade: dict) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.vstack(
                rx.text(trade["label"], size="2", weight="medium"),
                rx.text(trade["strategy_label"], size="1", color="var(--pfs-text-muted)"),
                spacing="0",
                align="start",
            ),
        ),
        rx.table.cell(trade["quantity"]),
        rx.table.cell(trade["fmt_premium"]),
        rx.table.cell(rx.text(trade["dte"], " d")),
        rx.table.cell(trade["opened_short"]),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    "Close",
                    on_click=lambda: OptionsTradingState.open_close_dialog(
                        trade["id"], False
                    ),
                    size="1",
                    variant="soft",
                ),
                rx.button(
                    "Expired",
                    on_click=lambda: OptionsTradingState.open_close_dialog(
                        trade["id"], True
                    ),
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.icon_button(
                    rx.icon("pencil", size=14),
                    on_click=lambda: OptionsTradingState.edit_trade(trade["id"]),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                ),
                rx.icon_button(
                    rx.icon("trash-2", size=14),
                    on_click=lambda: OptionsTradingState.confirm_delete(trade["id"]),
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                ),
                spacing="2",
            ),
        ),
    )


def _closed_row(trade: dict) -> rx.Component:
    return rx.table.row(
        rx.table.row_header_cell(
            rx.vstack(
                rx.text(trade["label"], size="2", weight="medium"),
                rx.text(trade["strategy_label"], size="1", color="var(--pfs-text-muted)"),
                spacing="0",
                align="start",
            ),
        ),
        rx.table.cell(trade["quantity"]),
        rx.table.cell(rx.text(trade["fmt_premium"], " / ", trade["fmt_exit"])),
        rx.table.cell(
            rx.text(trade["fmt_pnl"], color=trade["pnl_color"], weight="medium"),
        ),
        rx.table.cell(
            rx.badge(
                trade["status"], color_scheme=trade["status_badge_color"], variant="soft"
            ),
        ),
        rx.table.cell(rx.text(trade["held_days"], " d")),
        rx.table.cell(
            rx.icon_button(
                rx.icon("trash-2", size=14),
                on_click=lambda: OptionsTradingState.confirm_delete(trade["id"]),
                size="1",
                variant="ghost",
                color_scheme="gray",
            ),
        ),
    )


def _open_table() -> rx.Component:
    return rx.cond(
        OptionsTradingState.has_open_trades,
        rx.vstack(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Trade"),
                        rx.table.column_header_cell("Qty"),
                        rx.table.column_header_cell("Premium"),
                        rx.table.column_header_cell("DTE"),
                        rx.table.column_header_cell("Opened"),
                        rx.table.column_header_cell(""),
                    ),
                ),
                rx.table.body(rx.foreach(OptionsTradingState.open_trades, _open_row)),
                width="100%",
                size="1",
            ),
            rx.text(
                "Open positions show entry premium only; P/L is recorded "
                "when you close a trade with its exit price.",
                size="1",
                color="var(--pfs-text-muted)",
            ),
            spacing="2",
            width="100%",
        ),
        _empty("No open trades - log one above."),
    )


def _closed_table() -> rx.Component:
    return rx.cond(
        OptionsTradingState.has_closed_trades,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Trade"),
                    rx.table.column_header_cell("Qty"),
                    rx.table.column_header_cell("In / Out"),
                    rx.table.column_header_cell("P/L"),
                    rx.table.column_header_cell("Status"),
                    rx.table.column_header_cell("Held"),
                    rx.table.column_header_cell(""),
                ),
            ),
            rx.table.body(rx.foreach(OptionsTradingState.closed_trades, _closed_row)),
            width="100%",
            size="1",
        ),
        _empty("No closed trades yet."),
    )


def _close_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title(
                rx.cond(
                    OptionsTradingState.close_is_expire,
                    "Mark trade expired",
                    "Close trade",
                ),
            ),
            rx.alert_dialog.description(
                rx.text(OptionsTradingState.close_trade_label),
            ),
            rx.cond(
                OptionsTradingState.close_is_expire,
                rx.text(
                    "Expired worthless: exit price 0.00. A long position "
                    "loses its premium; a short position keeps it.",
                    size="1",
                    color="var(--pfs-text-muted)",
                    margin_top="8px",
                ),
                rx.vstack(
                    rx.text("Exit price ($/share)", size="1",
                            color="var(--pfs-text-muted)"),
                    rx.input(
                        value=OptionsTradingState.close_exit_price,
                        on_change=OptionsTradingState.set_close_price_input,
                        placeholder="e.g. 4.75",
                        size="2",
                        width="100%",
                    ),
                    spacing="1",
                    width="100%",
                    margin_top="8px",
                ),
            ),
            rx.cond(
                OptionsTradingState.close_error != "",
                rx.callout(
                    OptionsTradingState.close_error,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    margin_top="8px",
                ),
                rx.fragment(),
            ),
            rx.flex(
                rx.button(
                    "Cancel",
                    on_click=OptionsTradingState.cancel_close,
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.button(
                    rx.cond(
                        OptionsTradingState.close_is_expire,
                        "Mark Expired",
                        "Close Trade",
                    ),
                    on_click=OptionsTradingState.confirm_close,
                ),
                spacing="3",
                justify="end",
                margin_top="16px",
            ),
            max_width="400px",
        ),
        open=OptionsTradingState.show_close_dialog,
    )


def _delete_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete trade"),
            rx.alert_dialog.description(
                rx.text(
                    "Delete '",
                    OptionsTradingState.delete_confirm_label,
                    "'? This cannot be undone.",
                ),
            ),
            rx.flex(
                rx.button(
                    "Cancel",
                    on_click=OptionsTradingState.cancel_delete,
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.button(
                    "Delete",
                    color_scheme="red",
                    on_click=OptionsTradingState.execute_delete,
                ),
                spacing="3",
                justify="end",
                margin_top="16px",
            ),
            max_width="380px",
        ),
        open=OptionsTradingState.show_delete_confirm,
    )


def trades_section(performance_tab: rx.Component) -> rx.Component:
    """Tabbed trade log: open, closed, performance."""
    return content_card(
        rx.vstack(
            card_header(
                "Trade Log",
                rx.badge(
                    OptionsTradingState.open_trades.length(),
                    " open",
                    variant="soft",
                ),
                icon="clipboard-list",
            ),
            rx.cond(
                OptionsTradingState.trades_error != "",
                rx.callout(
                    OptionsTradingState.trades_error,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Open", value="open"),
                    rx.tabs.trigger("Closed", value="closed"),
                    rx.tabs.trigger("Performance", value="performance"),
                ),
                rx.tabs.content(_open_table(), value="open", padding_top="12px"),
                rx.tabs.content(_closed_table(), value="closed", padding_top="12px"),
                rx.tabs.content(
                    performance_tab, value="performance", padding_top="12px"
                ),
                value=OptionsTradingState.active_tab,
                on_change=OptionsTradingState.set_active_tab,
                width="100%",
            ),
            _close_dialog(),
            _delete_dialog(),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
