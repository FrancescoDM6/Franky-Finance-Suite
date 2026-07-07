"""Tests for options trade persistence (mocked db manager)."""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from phinan.modules.options import persistence


def sample_trade() -> dict:
    return {
        "ticker_symbol": "AAPL",
        "option_type": "call",
        "position_type": "long",
        "strategy": "long_call",
        "strike_price": 185.0,
        "premium": 3.55,
        "quantity": 2,
        "expiration_date": "2026-07-17",
        "opened_at": "2026-07-01 10:30:00",
        "notes": "range high play",
    }


@pytest.mark.integration
class TestAddTrade:
    def test_add_returns_sequence_id_and_inserts(self):
        db = MagicMock()
        db.query.return_value = [{"id": 11}]

        trade_id = persistence.add_trade(db, sample_trade())

        assert trade_id == 11
        insert_sql, params = db.execute.call_args.args
        assert "INSERT INTO options_positions" in insert_sql
        assert params[0] == 11
        assert params[1] == "AAPL"
        assert params[8] == "long_call"  # strategy
        assert "'open'" in insert_sql


@pytest.mark.integration
class TestListTrades:
    def test_list_open_filters_and_shapes_rows(self):
        db = MagicMock()
        db.query.return_value = [
            {
                "id": 1,
                "ticker_symbol": "AAPL",
                "option_type": "call",
                "strike_price": 185.0,
                "expiration_date": date(2026, 7, 17),
                "quantity": 2,
                "premium": 3.55,
                "position_type": "long",
                "strategy": "long_call",
                "status": "open",
                "exit_price": None,
                "realized_pnl": None,
                "opened_at": datetime(2026, 7, 1, 10, 30),
                "closed_at": None,
                "notes": "",
            }
        ]

        rows = persistence.list_trades(db, "open")

        sql = db.query.call_args.args[0]
        assert "status = 'open'" in sql
        assert rows[0]["expiration_date"] == "2026-07-17"
        assert rows[0]["opened_at"] == "2026-07-01 10:30:00"
        assert rows[0]["closed_at"] == ""
        assert rows[0]["realized_pnl"] is None

    def test_list_closed_uses_in_clause(self):
        db = MagicMock()
        db.query.return_value = []
        persistence.list_trades(db, "closed_or_expired")
        assert "IN ('closed', 'expired')" in db.query.call_args.args[0]


@pytest.mark.integration
class TestCloseUpdateDelete:
    def test_close_sets_status_exit_and_pnl(self):
        db = MagicMock()
        persistence.close_trade(db, 7, 4.75, 240.0, "closed", "2026-07-10 15:00:00")

        sql, params = db.execute.call_args.args
        assert "UPDATE options_positions" in sql
        assert params == ("closed", 4.75, 240.0, "2026-07-10 15:00:00", 7)

    def test_close_rejects_bad_status(self):
        db = MagicMock()
        with pytest.raises(ValueError, match="status"):
            persistence.close_trade(db, 7, 4.75, 240.0, "open")

    def test_update_whitelists_columns(self):
        db = MagicMock()
        persistence.update_trade(
            db, 7, {"premium": 3.6, "status": "closed", "id": 99, "notes": "x"}
        )

        sql, params = db.execute.call_args.args
        assert "premium = ?" in sql
        assert "notes = ?" in sql
        assert "status" not in sql  # not editable
        assert params[-1] == 7

    def test_update_with_no_editable_fields_is_noop(self):
        db = MagicMock()
        persistence.update_trade(db, 7, {"status": "closed"})
        db.execute.assert_not_called()

    def test_delete_executes(self):
        db = MagicMock()
        persistence.delete_trade(db, 5)
        sql, params = db.execute.call_args.args
        assert "DELETE FROM options_positions" in sql
        assert params == (5,)

    def test_count_closed(self):
        db = MagicMock()
        db.query.return_value = [{"n": 7}]
        assert persistence.count_closed_trades(db) == 7
