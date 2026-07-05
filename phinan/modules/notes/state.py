"""Notes module state.

Owns the terms form (string fields; parsing lives in form_logic.py), the
analysis status flags, and the simulation results as JSON-safe dicts.
Async orchestration lives in workflow.py (NotesWorkflowMixin) and
computed formatting in display_vars.py.
"""

import logging
from typing import Any

import reflex as rx

from .display_vars import TermsVarsMixin, ValuationVarsMixin
from .workflow import NotesWorkflowMixin

logger = logging.getLogger(__name__)

__all__ = ["NotesState"]


class NotesState(
    NotesWorkflowMixin,
    ValuationVarsMixin,
    TermsVarsMixin,
    rx.State,
):
    """State for the structured notes module."""

    # Terms form (strings for input binding; validated in form_logic)
    form_issuer: str = ""
    form_product_name: str = ""
    form_tickers: str = ""
    form_currency: str = "USD"
    form_notional: str = "1000"
    form_maturity_date: str = ""
    form_coupon_rate: str = ""
    form_coupon_frequency: str = "Quarterly"
    form_coupon_type: str = "Contingent"
    form_coupon_barrier: str = ""
    form_autocall_barrier: str = ""
    form_protection_barrier: str = ""
    form_barrier_type: str = "European"
    form_strike: str = "100"
    form_capital_protection: str = "0"

    # Advanced overrides (entered in percent; blank = settings default)
    override_risk_free: str = ""
    override_credit_spread: str = ""
    n_paths_choice: str = "10000"

    # Observation dates carried over from a parsed PDF (JSON dicts)
    _parsed_observation_dates: list[dict] = []

    # Status
    is_parsing: bool = False
    is_analyzing: bool = False
    analysis_stage: str = ""
    error_message: str = ""
    form_error: str = ""
    parse_warnings: list[str] = []
    terms_dirty: bool = False
    source_filename: str = ""

    # Backend-only: supersede counter for concurrent analysis runs
    _analysis_generation: int = 0

    # Results (JSON-safe dicts only - lean state)
    simulation: dict[str, Any] = {}
    outcome_histogram: list[dict[str, Any]] = []
    autocall_timeline: list[dict[str, Any]] = []
    alternatives: list[dict[str, Any]] = []
    narrative: str = ""
    narrative_error: str = ""
