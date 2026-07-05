"""Tests for structured note analysis persistence (mocked db manager)."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from phinan.models.structured_note import (
    AlternativeResult,
    NoteAnalysis,
    SimulationResult,
    StructuredNote,
)
from phinan.modules.notes import persistence


def make_analysis() -> NoteAnalysis:
    return NoteAnalysis(
        note=StructuredNote(
            issuer="UBS",
            product_name="Autocallable BRC",
            underlying_tickers=["AAPL", "MSFT"],
            maturity_date=date.today() + timedelta(days=730),
            coupon_rate_pa=9.0,
            coupon_type="Memory",
            protection_barrier=60.0,
        ),
        simulation=SimulationResult(
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
            percentiles={"p5": -0.3, "p50": 0.07, "p95": 0.12},
        ),
        alternatives=[
            AlternativeResult(
                strategy="Risk-free bond",
                expected_return_pct=0.09,
                expected_irr=0.045,
                max_loss_pct=0.0,
                p5=0.09,
                p50=0.09,
                p95=0.09,
                caveat="proxy",
            )
        ],
        narrative="A short take.",
    )


@pytest.mark.integration
class TestSaveAnalysis:
    def test_save_returns_sequence_id_and_inserts(self):
        db = MagicMock()
        db.query.return_value = [{"id": 7}]
        analysis = make_analysis()

        analysis_id = persistence.save_analysis(db, analysis, "sheet.pdf")

        assert analysis_id == 7
        insert_sql, params = db.execute.call_args.args
        assert "INSERT INTO structured_notes" in insert_sql
        assert params[0] == 7
        assert params[1] == "UBS - Autocallable BRC"  # label
        assert params[10] == "sheet.pdf"

    def test_label_falls_back_to_tickers(self):
        db = MagicMock()
        db.query.return_value = [{"id": 1}]
        analysis = make_analysis()
        analysis.note.issuer = ""
        analysis.note.product_name = ""

        persistence.save_analysis(db, analysis)

        _, params = db.execute.call_args.args
        assert params[1] == "AAPL, MSFT"


@pytest.mark.integration
class TestLoadAnalysis:
    def test_json_round_trip(self):
        original = make_analysis()
        db = MagicMock()
        db.query.return_value = [
            {
                "note_json": original.note.model_dump_json(),
                "valuation_json": original.simulation.model_dump_json(),
                "alternatives_json": (
                    "["
                    + ",".join(a.model_dump_json() for a in original.alternatives)
                    + "]"
                ),
                "narrative": original.narrative,
            }
        ]

        loaded = persistence.load_analysis(db, 7)

        assert loaded is not None
        assert loaded.note == original.note
        assert loaded.simulation == original.simulation
        assert loaded.alternatives == original.alternatives
        assert loaded.narrative == "A short take."

    def test_missing_row_returns_none(self):
        db = MagicMock()
        db.query.return_value = []
        assert persistence.load_analysis(db, 999) is None

    def test_corrupt_json_returns_none(self):
        db = MagicMock()
        db.query.return_value = [
            {"note_json": "{broken", "valuation_json": "{}", "narrative": ""}
        ]
        assert persistence.load_analysis(db, 1) is None


@pytest.mark.integration
class TestListAndDelete:
    def test_list_formats_rows(self):
        db = MagicMock()
        db.query.return_value = [
            {
                "id": 3,
                "label": "UBS - BRC",
                "issuer": "UBS",
                "source_filename": "a.pdf",
                "created_at": datetime(2026, 7, 5, 14, 30),
                "fair_value_pct": 0.93,
                "implied_fee_pct": 0.07,
            }
        ]

        rows = persistence.list_analyses(db)

        assert rows == [
            {
                "id": 3,
                "label": "UBS - BRC",
                "issuer": "UBS",
                "source_filename": "a.pdf",
                "created_at": "2026-07-05 14:30",
                "fair_value_pct": 0.93,
                "implied_fee_pct": 0.07,
            }
        ]

    def test_delete_executes(self):
        db = MagicMock()
        persistence.delete_analysis(db, 5)
        sql, params = db.execute.call_args.args
        assert "DELETE FROM structured_notes" in sql
        assert params == (5,)
