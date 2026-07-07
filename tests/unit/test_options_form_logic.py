"""Unit tests for the options trade form validation."""

import pytest

from phinan.modules.options.form_logic import (
    FormValidationError,
    derive_strategy,
    validate_close_form,
    validate_trade_form,
)


def valid_fields(**overrides) -> dict:
    fields = {
        "ticker": "aapl",
        "option_type": "call",
        "position_type": "long",
        "strategy": "long_call",
        "strike": "185",
        "premium": "3.55",
        "quantity": "2",
        "expiration_date": "2026-07-17",
        "opened_date": "2026-07-01",
        "notes": "range high play",
    }
    fields.update(overrides)
    return fields


@pytest.mark.unit
class TestValidateTradeForm:
    def test_valid_form_round_trip(self):
        trade = validate_trade_form(valid_fields())

        assert trade["ticker_symbol"] == "AAPL"
        assert trade["strike_price"] == 185.0
        assert trade["premium"] == 3.55
        assert trade["quantity"] == 2
        assert trade["expiration_date"] == "2026-07-17"
        assert trade["opened_at"].startswith("2026-07-01")
        assert trade["strategy"] == "long_call"

    def test_blank_opened_date_defaults_to_now(self):
        trade = validate_trade_form(valid_fields(opened_date=""))
        assert trade["opened_at"]  # populated

    def test_missing_ticker_rejected(self):
        with pytest.raises(FormValidationError, match="Ticker"):
            validate_trade_form(valid_fields(ticker="  "))

    def test_bad_strike_rejected(self):
        with pytest.raises(FormValidationError, match="Strike"):
            validate_trade_form(valid_fields(strike="lots"))

    def test_zero_premium_rejected(self):
        with pytest.raises(FormValidationError, match="Premium"):
            validate_trade_form(valid_fields(premium="0"))

    def test_fractional_contracts_rejected(self):
        with pytest.raises(FormValidationError, match="whole number"):
            validate_trade_form(valid_fields(quantity="1.5"))

    def test_bad_expiration_rejected(self):
        with pytest.raises(FormValidationError, match="YYYY-MM-DD"):
            validate_trade_form(valid_fields(expiration_date="July 17"))

    def test_inconsistent_strategy_rejected(self):
        # covered_call requires a SHORT call
        with pytest.raises(FormValidationError, match="covered_call"):
            validate_trade_form(
                valid_fields(strategy="covered_call", position_type="long")
            )

    def test_missing_strategy_derived(self):
        trade = validate_trade_form(
            valid_fields(strategy="", option_type="put", position_type="short")
        )
        assert trade["strategy"] == "cash_secured_put"


@pytest.mark.unit
class TestCloseFormAndDerive:
    def test_valid_exit_price(self):
        assert validate_close_form("4.75") == 4.75

    def test_zero_allowed_for_expiry(self):
        assert validate_close_form("0") == 0.0

    def test_negative_rejected(self):
        with pytest.raises(FormValidationError, match="negative"):
            validate_close_form("-1")

    def test_non_numeric_rejected(self):
        with pytest.raises(FormValidationError, match="number"):
            validate_close_form("a lot")

    def test_derive_strategy(self):
        assert derive_strategy("call", "short") == "covered_call"
        assert derive_strategy("put", "long") == "long_put"
