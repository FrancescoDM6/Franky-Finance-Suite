"""Unit tests for the notes terms form logic (pure, no Reflex)."""

from datetime import date, timedelta

import pytest

from phinan.models.structured_note import StructuredNote
from phinan.modules.notes.form_logic import (
    FORM_DEFAULTS,
    FormValidationError,
    build_note_from_form,
    form_from_note,
)

FUTURE = (date.today() + timedelta(days=730)).isoformat()


def valid_fields(**overrides) -> dict:
    fields = dict(FORM_DEFAULTS)
    fields.update(
        {
            "issuer": "UBS",
            "product_name": "Autocallable",
            "tickers": "aapl, msft",
            "maturity_date": FUTURE,
            "coupon_rate": "8.5",
            "coupon_barrier": "70",
            "autocall_barrier": "100",
            "protection_barrier": "60",
        }
    )
    fields.update(overrides)
    return fields


@pytest.mark.unit
class TestBuildNoteFromForm:
    def test_valid_form_builds_note(self):
        note = build_note_from_form(valid_fields())

        assert note.underlying_tickers == ["AAPL", "MSFT"]
        assert note.coupon_rate_pa == 8.5
        assert note.protection_barrier == 60.0
        assert note.maturity_date.isoformat() == FUTURE

    def test_missing_tickers_rejected(self):
        with pytest.raises(FormValidationError, match="ticker"):
            build_note_from_form(valid_fields(tickers="  "))

    def test_bad_maturity_format_rejected(self):
        with pytest.raises(FormValidationError, match="YYYY-MM-DD"):
            build_note_from_form(valid_fields(maturity_date="next year"))

    def test_past_maturity_rejected(self):
        with pytest.raises(FormValidationError, match="future"):
            build_note_from_form(valid_fields(maturity_date="2020-01-01"))

    def test_non_numeric_coupon_rejected(self):
        with pytest.raises(FormValidationError, match="Coupon rate"):
            build_note_from_form(valid_fields(coupon_rate="eight"))

    def test_out_of_range_barrier_rejected(self):
        with pytest.raises(FormValidationError, match="Protection barrier"):
            build_note_from_form(valid_fields(protection_barrier="450"))

    def test_optional_fields_may_be_blank(self):
        note = build_note_from_form(
            valid_fields(autocall_barrier="", coupon_barrier="", protection_barrier="")
        )
        assert note.autocall_barrier is None
        assert note.protection_barrier is None


@pytest.mark.unit
class TestRoundTrip:
    def test_note_survives_form_round_trip(self):
        original = StructuredNote(
            issuer="UBS",
            product_name="BRC",
            underlying_tickers=["AAPL", "MSFT"],
            maturity_date=date.today() + timedelta(days=365),
            coupon_rate_pa=9.0,
            coupon_frequency="Monthly",
            coupon_type="Memory",
            coupon_barrier=65.0,
            autocall_barrier=100.0,
            protection_barrier=55.0,
            barrier_type="American",
            strike_price=90.0,
            capital_protection=10.0,
        )

        rebuilt = build_note_from_form(form_from_note(original))

        for field in [
            "issuer",
            "underlying_tickers",
            "maturity_date",
            "coupon_rate_pa",
            "coupon_frequency",
            "coupon_type",
            "coupon_barrier",
            "autocall_barrier",
            "protection_barrier",
            "barrier_type",
            "strike_price",
            "capital_protection",
        ]:
            assert getattr(rebuilt, field) == getattr(original, field), field
