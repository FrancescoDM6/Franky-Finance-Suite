"""Options module state.

Owns the chain viewer data, the trade form (string fields; validation in
form_logic.py), the trade lists, and performance results as JSON-safe
dicts. Async orchestration lives in workflow.py and computed formatting
in display_vars.py.

Named OptionsTradingState because the research module already registers
a Reflex state class called OptionsState.
"""

import logging
from typing import Any

import reflex as rx

from .display_vars import (
    ChainVarsMixin,
    PerformanceVarsMixin,
    PreviewVarsMixin,
    TradesVarsMixin,
)
from .workflow import OptionsWorkflowMixin

logger = logging.getLogger(__name__)

__all__ = ["OptionsTradingState"]


class OptionsTradingState(
    OptionsWorkflowMixin,
    ChainVarsMixin,
    PreviewVarsMixin,
    TradesVarsMixin,
    PerformanceVarsMixin,
    rx.State,
):
    """State for the options trading module."""

    # Chain viewer
    chain_ticker: str = ""
    form_chain_ticker: str = ""
    show_autocomplete: bool = False
    chain_expirations: list[str] = []
    chain_expiration: str = ""
    chain_calls: list[dict[str, Any]] = []
    chain_puts: list[dict[str, Any]] = []
    chain_spot: float = 0.0
    chain_days_to_expiry: int = 0
    chain_loading: bool = False
    chain_error: str = ""

    # Trade form (strings for input binding)
    form_ticker: str = ""
    form_option_type: str = "call"
    form_position_type: str = "long"
    form_strategy: str = "long_call"
    form_strike: str = ""
    form_premium: str = ""
    form_quantity: str = "1"
    form_expiration: str = ""
    form_opened_date: str = ""
    form_notes: str = ""
    form_iv: str = ""
    form_error: str = ""
    editing_trade_id: int = 0

    # Strategy preview (JSON-safe dict from options_analytics)
    preview: dict[str, Any] = {}
    preview_error: str = ""

    # Trades
    open_trades: list[dict[str, Any]] = []
    closed_trades: list[dict[str, Any]] = []
    is_loading_trades: bool = False
    trades_error: str = ""

    # Close/expire dialog
    close_trade_id: int = 0
    close_trade_label: str = ""
    close_exit_price: str = ""
    close_is_expire: bool = False
    close_error: str = ""
    show_close_dialog: bool = False

    # Delete confirmation
    delete_confirm_id: int = 0
    delete_confirm_label: str = ""
    show_delete_confirm: bool = False

    # Performance
    performance: dict[str, Any] = {}

    # LLM pattern analysis
    pattern_analysis: str = ""
    pattern_error: str = ""
    is_analyzing_patterns: bool = False
    _pattern_generation: int = 0

    # UI
    active_tab: str = "open"
