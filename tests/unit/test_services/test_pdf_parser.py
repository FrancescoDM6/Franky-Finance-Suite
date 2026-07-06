"""Unit tests for the PDF parser service (JSON handling is LLM-free)."""

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from phinan.services.pdf_parser import PDFParserService, note_from_llm_json

FULL_PAYLOAD = {
    "issuer": "UBS",
    "product_name": "Autocallable BRC",
    "underlying_tickers": ["aapl", "MSFT"],
    "isin": "CH0012345678",
    "currency": "usd",
    "capital_protection": 0.0,
    "coupon_rate_pa": 9.5,
    "coupon_frequency": "quarterly",
    "coupon_type": "memory",
    "coupon_barrier": 70.0,
    "autocall_barrier": 100.0,
    "protection_barrier": 60.0,
    "strike_price": 100.0,
    "barrier_type": "daily",
    "maturity_date": "2028-07-05",
    "observation_dates": [
        {"date": "2026-10-05", "autocall_trigger": 100.0},
        {"date": "2027-01-05", "autocall_trigger": 95.0},
    ],
}


@pytest.mark.unit
class TestNoteFromLlmJson:
    def test_full_payload_parses_cleanly(self):
        note, warnings = note_from_llm_json(dict(FULL_PAYLOAD))

        assert warnings == []
        assert note.issuer == "UBS"
        assert note.underlying_tickers == ["AAPL", "MSFT"]
        assert note.currency == "USD"
        assert note.coupon_frequency == "Quarterly"
        assert note.coupon_type == "Memory"
        assert note.barrier_type == "American"  # "daily" alias
        assert note.maturity_date == date(2028, 7, 5)
        assert len(note.observation_dates) == 2
        assert note.observation_dates[1].autocall_trigger == 95.0

    def test_missing_fields_warn_but_still_build(self):
        note, warnings = note_from_llm_json({"issuer": "UBS"})

        assert note is not None
        assert note.issuer == "UBS"
        assert any("tickers" in w for w in warnings)
        assert any("Coupon rate" in w for w in warnings)
        assert any("Maturity" in w for w in warnings)

    def test_tickers_as_comma_string(self):
        note, _ = note_from_llm_json({"underlying_tickers": "aapl, msft"})
        assert note.underlying_tickers == ["AAPL", "MSFT"]

    def test_unknown_frequency_defaults_with_warning(self):
        note, warnings = note_from_llm_json({"coupon_frequency": "biweekly"})
        assert note.coupon_frequency == "Quarterly"
        assert any("coupon frequency" in w for w in warnings)

    def test_bad_date_warns_and_skips(self):
        payload = {
            "maturity_date": "sometime in 2028",
            "observation_dates": [{"date": "not-a-date"}],
        }
        note, warnings = note_from_llm_json(payload)
        assert note.maturity_date is None
        assert note.observation_dates == []
        assert any("maturity date" in w for w in warnings)

    def test_numeric_strings_parse(self):
        note, warnings = note_from_llm_json(
            {"coupon_rate_pa": "8.5", "protection_barrier": "60"}
        )
        assert note.coupon_rate_pa == 8.5
        assert note.protection_barrier == 60.0


@pytest.mark.unit
class TestCleanJson:
    def setup_method(self):
        self.service = PDFParserService()

    def test_json_code_block(self):
        text = 'Here you go:\n```json\n{"a": 1}\n```\nDone.'
        assert self.service._clean_json(text) == '{"a": 1}'

    def test_plain_code_block(self):
        text = '```\n{"a": 1}\n```'
        assert self.service._clean_json(text) == '{"a": 1}'

    def test_balanced_braces_in_prose(self):
        text = 'The extracted terms are {"a": {"b": 2}} as requested.'
        assert self.service._clean_json(text) == '{"a": {"b": 2}}'

    def test_raw_json_passthrough(self):
        assert self.service._clean_json(' {"a": 1} ') == '{"a": 1}'


@pytest.mark.unit
class TestParseTermSheet:
    def _service_with_llm(self, response: str, healthy: bool = True):
        service = PDFParserService()
        llm = MagicMock()
        llm.health_check.return_value = healthy
        llm.complete.return_value = response
        service._llm = llm
        return service

    def test_parses_llm_response(self):
        service = self._service_with_llm(
            "```json\n" + json.dumps(FULL_PAYLOAD) + "\n```"
        )
        note, warnings = service.parse_term_sheet("term sheet text")

        assert note is not None
        assert note.issuer == "UBS"
        assert warnings == []

    def test_llm_unavailable_returns_none_with_hint(self):
        service = self._service_with_llm("", healthy=False)
        note, warnings = service.parse_term_sheet("text")

        assert note is None
        assert any("manually" in w for w in warnings)

    def test_invalid_json_returns_none_with_hint(self):
        service = self._service_with_llm("I could not find any terms, sorry!")
        note, warnings = service.parse_term_sheet("text")

        assert note is None
        assert len(warnings) == 1

    def test_partial_json_returns_note_with_warnings(self):
        service = self._service_with_llm('{"issuer": "UBS"}')
        note, warnings = service.parse_term_sheet("text")

        assert note is not None
        assert note.issuer == "UBS"
        assert warnings  # missing tickers/coupon/maturity
