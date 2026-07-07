"""Pure trade-form validation for the Options module (no Reflex)."""

import logging
from datetime import date, datetime
from typing import Dict

from ...services.options_analytics import strategy_label

logger = logging.getLogger(__name__)

STRATEGIES = ["long_call", "long_put", "covered_call", "cash_secured_put"]
OPTION_TYPES = ["call", "put"]
POSITION_TYPES = ["long", "short"]

# Strategy -> required (option_type, position_type)
STRATEGY_CONSISTENCY = {
    "long_call": ("call", "long"),
    "long_put": ("put", "long"),
    "covered_call": ("call", "short"),
    "cash_secured_put": ("put", "short"),
}


class FormValidationError(ValueError):
    """A user-correctable problem with the trade form."""


def _required_float(value: str, label: str, lo: float, hi: float) -> float:
    try:
        parsed = float((value or "").strip())
    except ValueError:
        raise FormValidationError(f"{label} must be a number")
    if not (lo <= parsed <= hi):
        raise FormValidationError(f"{label} must be between {lo:g} and {hi:g}")
    return parsed


def derive_strategy(option_type: str, position_type: str) -> str:
    """Default strategy tag for a type/position pair."""
    return strategy_label(option_type, position_type)


def validate_trade_form(fields: Dict[str, str]) -> dict:
    """Validate trade form fields into a dict typed for persistence.

    Raises FormValidationError with a user-facing message on the first
    invalid field.
    """
    ticker = (fields.get("ticker") or "").strip().upper()
    if not ticker:
        raise FormValidationError("Ticker is required")

    option_type = fields.get("option_type") or ""
    if option_type not in OPTION_TYPES:
        raise FormValidationError("Option type must be call or put")
    position_type = fields.get("position_type") or ""
    if position_type not in POSITION_TYPES:
        raise FormValidationError("Position must be long or short")

    strategy = fields.get("strategy") or derive_strategy(option_type, position_type)
    if strategy not in STRATEGIES:
        raise FormValidationError(f"Strategy must be one of {STRATEGIES}")
    expected = STRATEGY_CONSISTENCY[strategy]
    if (option_type, position_type) != expected:
        raise FormValidationError(
            f"{strategy} means a {expected[1]} {expected[0]} - "
            "adjust the strategy or the option type/position"
        )

    strike = _required_float(fields.get("strike"), "Strike", 0.01, 1e6)
    premium = _required_float(fields.get("premium"), "Premium", 0.0, 1e5)
    if premium <= 0:
        raise FormValidationError("Premium must be positive")

    quantity_raw = (fields.get("quantity") or "").strip()
    try:
        quantity = int(quantity_raw)
    except ValueError:
        raise FormValidationError("Contracts must be a whole number")
    if quantity < 1:
        raise FormValidationError("Contracts must be at least 1")

    expiration_raw = (fields.get("expiration_date") or "").strip()
    try:
        expiration = date.fromisoformat(expiration_raw)
    except ValueError:
        raise FormValidationError("Expiration must be YYYY-MM-DD")

    opened_raw = (fields.get("opened_date") or "").strip()
    if opened_raw:
        try:
            opened_at = datetime.fromisoformat(opened_raw)
        except ValueError:
            raise FormValidationError("Opened date must be YYYY-MM-DD")
    else:
        opened_at = datetime.now()

    return {
        "ticker_symbol": ticker,
        "option_type": option_type,
        "position_type": position_type,
        "strategy": strategy,
        "strike_price": strike,
        "premium": premium,
        "quantity": quantity,
        "expiration_date": expiration.isoformat(),
        "opened_at": opened_at.isoformat(sep=" ", timespec="seconds"),
        "notes": (fields.get("notes") or "").strip(),
    }


def validate_close_form(exit_price: str) -> float:
    """Validate the manual exit price for the close dialog."""
    try:
        parsed = float((exit_price or "").strip())
    except ValueError:
        raise FormValidationError("Exit price must be a number")
    if parsed < 0:
        raise FormValidationError("Exit price cannot be negative")
    return parsed
