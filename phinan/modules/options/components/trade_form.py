"""Trade logging form for the Options module."""

import reflex as rx

from ....components.ui import card_header, content_card
from ..form_logic import STRATEGIES
from ..state import OptionsTradingState


def _label(text: str) -> rx.Component:
    return rx.text(text, size="1", color="var(--pfs-text-muted)")


def _text_field(label: str, field: str, value, placeholder: str = "") -> rx.Component:
    return rx.vstack(
        _label(label),
        rx.input(
            value=value,
            on_change=lambda v: OptionsTradingState.set_form_field(field, v),
            placeholder=placeholder,
            size="2",
            width="100%",
        ),
        spacing="1",
        width="100%",
    )


def _select_field(label: str, field: str, value, options: list[str]) -> rx.Component:
    return rx.vstack(
        _label(label),
        rx.select(
            options,
            value=value,
            on_change=lambda v: OptionsTradingState.set_form_field(field, v),
            size="2",
            width="100%",
        ),
        spacing="1",
        width="100%",
    )


def trade_form() -> rx.Component:
    """Manual trade entry (prefillable from the chain viewer)."""
    return content_card(
        rx.vstack(
            card_header(
                "Log a Trade",
                rx.cond(
                    OptionsTradingState.is_editing,
                    rx.badge("Editing", color_scheme="amber", variant="soft"),
                    rx.fragment(),
                ),
                icon="notebook-pen",
            ),
            _text_field("Ticker", "ticker", OptionsTradingState.form_ticker, "AAPL"),
            rx.hstack(
                _select_field(
                    "Type", "option_type", OptionsTradingState.form_option_type,
                    ["call", "put"],
                ),
                _select_field(
                    "Position", "position_type", OptionsTradingState.form_position_type,
                    ["long", "short"],
                ),
                spacing="2",
                width="100%",
            ),
            _select_field(
                "Strategy", "strategy", OptionsTradingState.form_strategy, STRATEGIES
            ),
            rx.hstack(
                _text_field("Strike $", "strike", OptionsTradingState.form_strike, "185"),
                _text_field(
                    "Premium $/share", "premium", OptionsTradingState.form_premium, "3.55"
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _text_field("Contracts", "quantity", OptionsTradingState.form_quantity),
                _text_field(
                    "Expiration", "expiration", OptionsTradingState.form_expiration,
                    "YYYY-MM-DD",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _text_field(
                    "Opened (blank = today)", "opened_date",
                    OptionsTradingState.form_opened_date, "YYYY-MM-DD",
                ),
                _text_field(
                    "IV % (for preview)", "iv", OptionsTradingState.form_iv, "35"
                ),
                spacing="2",
                width="100%",
            ),
            _text_field("Notes", "notes", OptionsTradingState.form_notes),
            rx.cond(
                OptionsTradingState.form_error != "",
                rx.callout(
                    OptionsTradingState.form_error,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.hstack(
                rx.button(
                    rx.icon("plus", size=16),
                    rx.cond(
                        OptionsTradingState.is_editing, "Update Trade", "Log Trade"
                    ),
                    on_click=OptionsTradingState.log_trade,
                    size="2",
                    flex="1",
                ),
                rx.cond(
                    OptionsTradingState.is_editing,
                    rx.button(
                        "Cancel",
                        on_click=OptionsTradingState.cancel_edit,
                        variant="soft",
                        color_scheme="gray",
                        size="2",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
