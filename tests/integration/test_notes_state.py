"""Integration tests for the Notes module state workflow."""

import asyncio
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from phinan.models.structured_note import (
    NoteAnalysis,
    OutcomeBucket,
    SimulationResult,
    StructuredNote,
)

FUTURE = (date.today() + timedelta(days=730)).isoformat()


class FakeUploadFile:
    name = "term_sheet.pdf"

    async def read(self) -> bytes:
        return b"%PDF-fake"


def make_parsed_note() -> StructuredNote:
    return StructuredNote(
        issuer="UBS",
        product_name="Autocallable BRC",
        underlying_tickers=["AAPL"],
        maturity_date=date.today() + timedelta(days=730),
        coupon_rate_pa=9.0,
        protection_barrier=60.0,
        autocall_barrier=100.0,
        coupon_barrier=70.0,
    )


def make_analysis(note: StructuredNote) -> NoteAnalysis:
    simulation = SimulationResult(
        fair_value_pct=0.93,
        bond_floor_pct=0.89,
        option_value_pct=0.04,
        implied_fee_pct=0.07,
        expected_return_pct=0.06,
        expected_irr=0.055,
        median_irr=0.06,
        prob_autocall=0.55,
        prob_barrier_breach=0.2,
        prob_loss=0.18,
        expected_life_years=1.2,
        percentiles={"p5": -0.3, "p25": 0.02, "p50": 0.07, "p75": 0.09, "p95": 0.12},
        histogram=[OutcomeBucket(label="+0%", low=0.0, high=0.05, pct=100.0)],
        n_paths=2000,
        seed=1,
        risk_free_rate=0.045,
        credit_spread=0.01,
        correlation_used=0.6,
        vols_used={"AAPL": 0.25},
        spots_used={"AAPL": 200.0},
    )
    return NoteAnalysis(note=note, simulation=simulation)


def make_state():
    from phinan.modules.notes.state import NotesState

    return NotesState()


def fill_valid_form(state) -> None:
    state.form_issuer = "UBS"
    state.form_tickers = "AAPL"
    state.form_maturity_date = FUTURE
    state.form_coupon_rate = "9.0"
    state.form_coupon_barrier = "70"
    state.form_autocall_barrier = "100"
    state.form_protection_barrier = "60"


async def exhaust(agen) -> None:
    async for _ in agen:
        pass


@pytest.mark.integration
class TestUploadFlow:
    def test_upload_fills_form_without_running_analysis(self):
        with patch("phinan.services.services") as services:
            services.pdf_parser.extract_text.return_value = "term sheet text"
            services.pdf_parser.parse_term_sheet.return_value = (
                make_parsed_note(),
                ["Coupon barrier assumed from text"],
            )

            state = make_state()
            asyncio.run(exhaust(state.handle_upload([FakeUploadFile()])))

        assert state.form_tickers == "AAPL"
        assert state.form_coupon_rate == "9"
        assert state.parse_warnings == ["Coupon barrier assumed from text"]
        assert state.has_analysis is False
        assert state.is_parsing is False
        assert state.source_filename == "term_sheet.pdf"

    def test_empty_pdf_text_sets_error(self):
        with patch("phinan.services.services") as services:
            services.pdf_parser.extract_text.return_value = "   "

            state = make_state()
            asyncio.run(exhaust(state.handle_upload([FakeUploadFile()])))

        assert "No text could be extracted" in state.error_message
        assert state.form_tickers == ""

    def test_failed_parse_surfaces_hint(self):
        with patch("phinan.services.services") as services:
            services.pdf_parser.extract_text.return_value = "some text"
            services.pdf_parser.parse_term_sheet.return_value = (
                None,
                ["AI extraction unavailable - enter the terms manually"],
            )

            state = make_state()
            asyncio.run(exhaust(state.handle_upload([FakeUploadFile()])))

        assert "manually" in state.error_message


@pytest.mark.integration
class TestRunAnalysis:
    def test_happy_path_stores_results(self):
        note = make_parsed_note()
        with patch("phinan.services.services") as services:
            services.structured_products.build_market_inputs.return_value = MagicMock()
            services.structured_products.analyze_note.return_value = make_analysis(note)

            state = make_state()
            fill_valid_form(state)
            asyncio.run(exhaust(state.run_analysis()))

        assert state.has_analysis is True
        assert state.simulation["fair_value_pct"] == 0.93
        assert len(state.outcome_histogram) == 1
        assert state.is_analyzing is False
        assert state.terms_dirty is False
        assert state.error_message == ""
        services.structured_products.analyze_note.assert_called_once()

    def test_form_error_short_circuits(self):
        with patch("phinan.services.services") as services:
            state = make_state()
            fill_valid_form(state)
            state.form_tickers = ""  # invalid

            asyncio.run(exhaust(state.run_analysis()))

        assert "ticker" in state.form_error
        assert state.has_analysis is False
        services.structured_products.analyze_note.assert_not_called()

    def test_market_data_failure_sets_error(self):
        with patch("phinan.services.services") as services:
            services.structured_products.build_market_inputs.side_effect = ValueError(
                "Could not fetch market data for: ZZZZ"
            )

            state = make_state()
            fill_valid_form(state)
            asyncio.run(exhaust(state.run_analysis()))

        assert "ZZZZ" in state.error_message
        assert state.is_analyzing is False
        services.structured_products.analyze_note.assert_not_called()

    def test_superseded_run_discards_results(self):
        note = make_parsed_note()
        with patch("phinan.services.services") as services:
            services.structured_products.build_market_inputs.return_value = MagicMock()
            services.structured_products.analyze_note.return_value = make_analysis(note)

            state = make_state()
            fill_valid_form(state)

            async def run_superseded():
                gen = state.run_analysis()
                await gen.__anext__()  # first yield, generation captured
                state._analysis_generation += 1  # a newer run started
                async for _ in gen:
                    pass

            asyncio.run(run_superseded())

        assert state.has_analysis is False
        # The stale run must not clear the (notional) newer run's spinner
        assert state.is_analyzing is True

    def test_editing_form_after_analysis_marks_dirty(self):
        note = make_parsed_note()
        with patch("phinan.services.services") as services:
            services.structured_products.build_market_inputs.return_value = MagicMock()
            services.structured_products.analyze_note.return_value = make_analysis(note)

            state = make_state()
            fill_valid_form(state)
            asyncio.run(exhaust(state.run_analysis()))

            assert state.terms_dirty is False
            state.set_form_field("coupon_rate", "10.0")

        assert state.terms_dirty is True
        assert state.has_analysis is True  # results kept, just badged stale

    def test_clear_all_resets_everything(self):
        note = make_parsed_note()
        with patch("phinan.services.services") as services:
            services.structured_products.build_market_inputs.return_value = MagicMock()
            services.structured_products.analyze_note.return_value = make_analysis(note)

            state = make_state()
            fill_valid_form(state)
            asyncio.run(exhaust(state.run_analysis()))
            state.clear_all()

        assert state.has_analysis is False
        assert state.form_tickers == ""
        assert state.simulation == {}
