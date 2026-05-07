"""Portfolio page - Manage your stock positions.

Shows holdings with current values, P/L, and allows adding new positions.
"""

import reflex as rx

from ...components.layout import main_layout
from ...state.user_context import UserContextState
from .state import PortfolioState, PortfolioPosition


def portfolio_summary() -> rx.Component:
    """Summary card showing total portfolio value."""
    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text("Total Value", size="1", color_scheme="gray"),
                rx.text(
                    rx.cond(
                        PortfolioState.has_positions,
                        PortfolioState.fmt_total_value,
                        "$0.00",
                    ),
                    size="6",
                    weight="bold",
                ),
                align="start",
                spacing="1",
            ),
            rx.vstack(
                rx.text("Total Cost", size="1", color_scheme="gray"),
                rx.text(
                    rx.cond(
                        PortfolioState.has_positions,
                        PortfolioState.fmt_total_cost,
                        "$0.00",
                    ),
                    size="4",
                    weight="medium",
                ),
                align="start",
                spacing="1",
            ),
            rx.vstack(
                rx.text("Unrealized P/L", size="1", color_scheme="gray"),
                rx.hstack(
                    rx.text(
                        PortfolioState.fmt_total_gain_loss,
                        size="4",
                        weight="medium",
                        color=PortfolioState.total_gain_loss_color,
                    ),
                    rx.badge(
                        PortfolioState.fmt_total_pl_pct,
                        color_scheme=PortfolioState.total_gain_loss_badge_color,
                        variant="soft",
                    ),
                    spacing="2",
                    align="center",
                ),
                align="start",
                spacing="1",
            ),
            justify="between",
            width="100%",
            wrap="wrap",
        ),
        width="100%",
    )



def position_row(position: PortfolioPosition) -> rx.Component:
    """Single position row in the table."""
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(position.ticker_symbol, weight="bold"),
                spacing="2",
            )
        ),
        rx.table.cell(rx.text(position.fmt_quantity)),
        rx.table.cell(rx.text(position.fmt_cost_basis)),
        rx.table.cell(rx.text(position.fmt_current_price)),
        rx.table.cell(rx.text(position.fmt_current_value)),
        rx.table.cell(
            rx.hstack(
                rx.text(
                    position.fmt_gain_loss,
                    color=position.gain_loss_color,
                ),
                rx.badge(
                    position.fmt_gain_loss_percent,
                    color_scheme=position.gain_loss_badge_color,
                    variant="soft",
                    size="1",
                ),
                spacing="2",
            )
        ),
        rx.table.cell(
            rx.icon_button(
                rx.icon("trash-2", size=14),
                size="1",
                color_scheme="red",
                variant="ghost",
                on_click=lambda: PortfolioState.confirm_delete_position(position.id),
            )
        ),
    )



def delete_confirmation_dialog() -> rx.Component:
    """Confirmation dialog for deleting a position."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete Position"),
            rx.alert_dialog.description(
                rx.text(
                    "Are you sure you want to delete your ",
                    rx.text(PortfolioState.delete_confirm_ticker, weight="bold"),
                    " position? This action cannot be undone.",
                ),
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=PortfolioState.cancel_delete,
                    ),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=PortfolioState.execute_delete,
                    ),
                ),
                spacing="3",
                justify="end",
                width="100%",
            ),
            style={"max_width": "450px"},
        ),
        open=PortfolioState.show_delete_confirm,
    )


def positions_table() -> rx.Component:

    """Table of all positions."""
    return rx.cond(
        PortfolioState.has_positions,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Symbol"),
                    rx.table.column_header_cell("Quantity"),
                    rx.table.column_header_cell("Cost Basis"),
                    rx.table.column_header_cell("Current"),
                    rx.table.column_header_cell("Value"),
                    rx.table.column_header_cell("P/L"),
                    rx.table.column_header_cell(""),
                ),
            ),
            rx.table.body(
                rx.foreach(PortfolioState.positions, position_row),
            ),
            width="100%",
        ),
        rx.center(
            rx.vstack(
                # Custom Shark Fin Icon (Empty State)
                rx.html(
                    """
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--gray-8)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M 4 20 C 10 18 16 11 19 6 Q 23 13 20 20" />
                        <polyline points="16 3 22 3 23 8" />
                    </svg>
                    """
                ),
                rx.text("Start deep dive", size="3", weight="bold", color_scheme="gray"),
                rx.text(
                    "Add your first position to start tracking your portfolio",
                    size="2",
                    color_scheme="gray",
                ),
                spacing="2",
                align="center",
            ),
            padding="8",
        ),
    )


def add_position_form() -> rx.Component:
    """Form to add a new position."""
    return rx.cond(
        PortfolioState.show_add_form,
        rx.card(
            rx.vstack(
                rx.heading("Add Position", size="4"),
                rx.cond(
                    PortfolioState.error_message != "",
                    rx.callout(
                        PortfolioState.error_message,
                        icon="circle-alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.fragment(),
                ),
                rx.grid(
                    rx.vstack(
                        rx.text("Ticker Symbol", size="1", weight="medium"),
                        rx.box(
                            rx.input(
                                placeholder="Search ticker...",
                                value=PortfolioState.form_ticker,
                                on_change=PortfolioState.set_form_ticker,
                                width="100%",
                            ),
                            rx.cond(
                                PortfolioState.show_autocomplete,
                                rx.box(
                                    rx.vstack(
                                        rx.foreach(
                                            PortfolioState.ticker_options,
                                            lambda opt: rx.box(
                                                rx.text(opt, size="1"),
                                                padding="8px",
                                                cursor="pointer",
                                                _hover={"background": "var(--accent-a3)"},
                                                on_click=lambda: PortfolioState.select_ticker(opt),
                                                width="100%",
                                            ),
                                        ),
                                        spacing="0",
                                        width="100%",
                                    ),
                                    position="absolute",
                                    top="100%",
                                    left="0",
                                    right="0",
                                    background="var(--color-background)",
                                    border="1px solid var(--gray-a6)",
                                    border_radius="6px",
                                    box_shadow="0 4px 12px rgba(0,0,0,0.15)",
                                    z_index="100",
                                    max_height="200px",
                                    overflow_y="auto",
                                ),
                                rx.fragment(),
                            ),
                            position="relative",
                            width="100%",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.vstack(
                        rx.text("Quantity", size="1", weight="medium"),
                        rx.input(
                            placeholder="10",
                            type="number",
                            min="0.01",
                            step="0.01",
                            value=PortfolioState.form_quantity,
                            on_change=PortfolioState.set_form_quantity,
                            width="100%",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.vstack(
                        rx.text("Cost Basis (per share)", size="1", weight="medium"),
                        rx.input(
                            placeholder="150.00",
                            type="number",
                            min="0.01",
                            step="0.01",
                            value=PortfolioState.form_cost_basis,
                            on_change=PortfolioState.set_form_cost_basis,
                            width="100%",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    rx.vstack(
                        rx.text("Purchase Date", size="1", weight="medium"),
                        rx.input(
                            type="date",
                            value=PortfolioState.form_purchase_date,
                            on_change=PortfolioState.set_form_purchase_date,
                            width="100%",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    columns=rx.breakpoints({"0px": "1", "640px": "2", "768px": "4"}),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Notes (optional)", size="1", weight="medium"),
                    rx.input(
                        placeholder="Why I bought this...",
                        value=PortfolioState.form_notes,
                        on_change=PortfolioState.set_form_notes,
                        width="100%",
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=PortfolioState.toggle_add_form,
                    ),
                    rx.button(
                        "Add Position",
                        on_click=PortfolioState.add_position,
                    ),
                    spacing="2",
                    justify="end",
                ),
                spacing="4",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


def portfolio_content() -> rx.Component:
    """Portfolio page content."""
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.heading("Portfolio", size="6"),
                rx.text(
                    "Track your stock positions and performance.",
                    size="2",
                    color_scheme="gray",
                ),
                align="start",
            ),
            rx.button(
                rx.icon("plus", size=16),
                "Add Position",
                on_click=PortfolioState.toggle_add_form,
                variant=rx.cond(PortfolioState.show_add_form, "soft", "solid"),
            ),
            justify="between",
            align="center",
            width="100%",
        ),
        rx.divider(),
        rx.cond(
            PortfolioState.is_loading,
            rx.center(
                rx.spinner(size="3"),
                padding="8",
            ),
            rx.vstack(
                portfolio_summary(),
                add_position_form(),
                positions_table(),
                delete_confirmation_dialog(),
                spacing="4",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
        max_width="1000px",
    )


@rx.page(
    route="/portfolio",
    title="Portfolio | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions, PortfolioState.load_tickers],
)
def portfolio_page() -> rx.Component:
    """Portfolio page."""
    return main_layout(portfolio_content())
