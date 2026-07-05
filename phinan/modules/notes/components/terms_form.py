"""Editable note terms form - the term-accuracy loop.

Every field the analysis depends on is visible and correctable here,
whether it came from the PDF extraction or manual entry.
"""

import reflex as rx

from ....components.ui import card_header, content_card
from ..form_logic import BARRIER_TYPES, COUPON_FREQUENCIES, COUPON_TYPES
from ..state import NotesState


def _label(text: str) -> rx.Component:
    return rx.text(text, size="1", color="var(--pfs-text-muted)")


def _text_field(label: str, field: str, value, placeholder: str = "") -> rx.Component:
    return rx.vstack(
        _label(label),
        rx.input(
            value=value,
            on_change=lambda v: NotesState.set_form_field(field, v),
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
            on_change=lambda v: NotesState.set_form_field(field, v),
            size="2",
            width="100%",
        ),
        spacing="1",
        width="100%",
    )


def _advanced_settings() -> rx.Component:
    """Market assumption overrides (blank = configured defaults)."""
    return rx.accordion.root(
        rx.accordion.item(
            header=rx.text("Advanced assumptions", size="1"),
            content=rx.vstack(
                _text_field(
                    "Risk-free rate % (blank = default)",
                    "override_risk_free",
                    NotesState.override_risk_free,
                    "4.5",
                ),
                _text_field(
                    "Issuer credit spread % (blank = default)",
                    "override_credit_spread",
                    NotesState.override_credit_spread,
                    "1.0",
                ),
                rx.vstack(
                    _label("Simulation paths"),
                    rx.select(
                        ["2000", "10000", "25000"],
                        value=NotesState.n_paths_choice,
                        on_change=NotesState.set_n_paths_choice,
                        size="2",
                        width="100%",
                    ),
                    spacing="1",
                    width="100%",
                ),
                spacing="2",
                width="100%",
                padding_y="8px",
            ),
        ),
        collapsible=True,
        type="single",
        width="100%",
        variant="ghost",
    )


def terms_form() -> rx.Component:
    """The note terms input form with the Analyze action."""
    return content_card(
        rx.vstack(
            card_header(
                "Note Terms",
                rx.cond(
                    NotesState.terms_dirty,
                    rx.badge("Edited - re-analyze", color_scheme="amber", variant="soft"),
                    rx.fragment(),
                ),
                icon="list-checks",
            ),
            _text_field("Issuer", "issuer", NotesState.form_issuer, "e.g. UBS"),
            _text_field(
                "Product name",
                "product_name",
                NotesState.form_product_name,
                "e.g. Autocallable BRC",
            ),
            _text_field(
                "Underlying tickers (comma separated)",
                "tickers",
                NotesState.form_tickers,
                "e.g. AAPL, MSFT",
            ),
            rx.hstack(
                _text_field(
                    "Maturity (YYYY-MM-DD)",
                    "maturity_date",
                    NotesState.form_maturity_date,
                    "2028-07-05",
                ),
                _text_field("Currency", "currency", NotesState.form_currency),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _text_field(
                    "Coupon % p.a.", "coupon_rate", NotesState.form_coupon_rate, "8.0"
                ),
                _select_field(
                    "Frequency",
                    "coupon_frequency",
                    NotesState.form_coupon_frequency,
                    COUPON_FREQUENCIES,
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _select_field(
                    "Coupon type",
                    "coupon_type",
                    NotesState.form_coupon_type,
                    COUPON_TYPES,
                ),
                rx.cond(
                    NotesState.coupon_needs_barrier,
                    _text_field(
                        "Coupon barrier %",
                        "coupon_barrier",
                        NotesState.form_coupon_barrier,
                        "70",
                    ),
                    rx.fragment(),
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _text_field(
                    "Autocall barrier %",
                    "autocall_barrier",
                    NotesState.form_autocall_barrier,
                    "100",
                ),
                _text_field(
                    "Protection barrier %",
                    "protection_barrier",
                    NotesState.form_protection_barrier,
                    "60",
                ),
                spacing="2",
                width="100%",
            ),
            rx.hstack(
                _select_field(
                    "Barrier type",
                    "barrier_type",
                    NotesState.form_barrier_type,
                    BARRIER_TYPES,
                ),
                _text_field("Strike %", "strike", NotesState.form_strike),
                _text_field(
                    "Protection %",
                    "capital_protection",
                    NotesState.form_capital_protection,
                ),
                spacing="2",
                width="100%",
            ),
            _advanced_settings(),
            rx.cond(
                NotesState.form_error != "",
                rx.callout(
                    NotesState.form_error,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.button(
                rx.icon("play", size=16),
                "Analyze Note",
                on_click=NotesState.run_analysis,
                loading=NotesState.is_analyzing,
                size="3",
                width="100%",
            ),
            rx.cond(
                NotesState.is_analyzing,
                rx.text(
                    NotesState.analysis_stage,
                    size="1",
                    color="var(--pfs-text-muted)",
                ),
                rx.fragment(),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
