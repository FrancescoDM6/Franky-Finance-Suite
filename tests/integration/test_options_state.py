"""Integration tests for the Options module state workflow."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def make_state():
    from phinan.modules.options.state import OptionsTradingState

    return OptionsTradingState()


async def make_state_with_tree(token: str):
    """State attached to a real in-memory tree (get_state works)."""
    from phinan.modules.options.state import OptionsTradingState
    from phinan.state.user_context import UserContextState
    from reflex.istate.manager.memory import StateManagerMemory

    manager = StateManagerMemory.create(OptionsTradingState.get_root_state())
    root = await manager.get_state(token)
    state = root.get_substate(OptionsTradingState.get_full_name().split("."))
    await state.get_state(UserContextState)
    return state


def open_trade_row(trade_id: int = 1, **overrides) -> dict:
    row = {
        "id": trade_id,
        "ticker_symbol": "AAPL",
        "option_type": "call",
        "strike_price": 185.0,
        "expiration_date": "2026-09-18",
        "quantity": 2,
        "premium": 3.55,
        "position_type": "long",
        "strategy": "long_call",
        "status": "open",
        "exit_price": None,
        "realized_pnl": None,
        "opened_at": "2026-07-01 10:30:00",
        "closed_at": "",
        "notes": "",
    }
    row.update(overrides)
    return row


def closed_trade_row(trade_id: int, pnl: float, **overrides) -> dict:
    row = open_trade_row(trade_id)
    row.update(
        {
            "status": "closed",
            "exit_price": 4.75,
            "realized_pnl": pnl,
            "closed_at": "2026-07-10 15:00:00",
        }
    )
    row.update(overrides)
    return row


def fill_valid_form(state) -> None:
    state.form_ticker = "AAPL"
    state.form_option_type = "call"
    state.form_position_type = "long"
    state.form_strategy = "long_call"
    state.form_strike = "185"
    state.form_premium = "3.55"
    state.form_quantity = "2"
    state.form_expiration = "2026-09-18"


async def exhaust(agen) -> None:
    async for _ in agen:
        pass


@pytest.mark.integration
class TestTradeLogging:
    def test_log_trade_inserts_and_reloads(self):
        with patch("phinan.services.services"):
            with patch(
                "phinan.modules.options.workflow.persistence"
            ) as persistence:
                persistence.add_trade.return_value = 1
                persistence.list_trades.side_effect = [
                    [open_trade_row(1)],  # open
                    [],  # closed
                ]

                state = make_state()
                fill_valid_form(state)
                asyncio.run(state.log_trade())

        persistence.add_trade.assert_called_once()
        assert len(state.open_trades) == 1
        assert state.open_trades[0]["label"] == "AAPL $185C 09/18"
        assert state.form_ticker == ""  # form cleared
        assert state.form_error == ""

    def test_invalid_form_short_circuits(self):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                state = make_state()
                fill_valid_form(state)
                state.form_premium = "free"

                asyncio.run(state.log_trade())

        persistence.add_trade.assert_not_called()
        assert "Premium" in state.form_error

    def test_edit_trade_prefills_form_and_updates(self):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                persistence.list_trades.side_effect = [
                    [open_trade_row(7)],
                    [],
                    [open_trade_row(7, premium=4.0)],
                    [],
                ]

                state = make_state()
                asyncio.run(state._reload_trades())
                state.edit_trade(7)

                assert state.editing_trade_id == 7
                assert state.form_ticker == "AAPL"
                assert state.form_premium == "3.55"

                state.set_form_field("premium", "4.0")
                asyncio.run(state.log_trade())

        persistence.update_trade.assert_called_once()
        assert persistence.update_trade.call_args.args[1] == 7
        assert state.editing_trade_id == 0


@pytest.mark.integration
class TestCloseFlow:
    def _run_close(self, exit_price: str, expire: bool):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                persistence.list_trades.side_effect = [
                    [open_trade_row(1)], [],  # initial load
                    [], [closed_trade_row(1, 240.0)],  # after close
                ]

                state = make_state()
                asyncio.run(state._reload_trades())
                state.open_close_dialog(1, expire)
                if not expire:
                    state.set_close_price_input(exit_price)
                asyncio.run(state.confirm_close())
                return state, persistence

    def test_close_with_exit_price_computes_pnl(self):
        state, persistence = self._run_close("4.75", expire=False)

        args = persistence.close_trade.call_args.args
        # (db, trade_id, exit_price, pnl, status)
        assert args[1] == 1
        assert args[2] == 4.75
        assert args[3] == pytest.approx((4.75 - 3.55) * 100 * 2)
        assert args[4] == "closed"
        assert state.show_close_dialog is False
        assert len(state.closed_trades) == 1

    def test_expire_forces_exit_zero(self):
        state, persistence = self._run_close("ignored", expire=True)

        args = persistence.close_trade.call_args.args
        assert args[2] == 0.0
        assert args[3] == pytest.approx(-3.55 * 100 * 2)
        assert args[4] == "expired"

    def test_invalid_exit_price_keeps_dialog_open(self):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                persistence.list_trades.side_effect = [[open_trade_row(1)], []]

                state = make_state()
                asyncio.run(state._reload_trades())
                state.open_close_dialog(1, False)
                state.set_close_price_input("many dollars")
                asyncio.run(state.confirm_close())

        persistence.close_trade.assert_not_called()
        assert state.show_close_dialog is True
        assert "number" in state.close_error


@pytest.mark.integration
class TestDeleteFlow:
    def test_delete_requires_confirmation(self):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                persistence.list_trades.side_effect = [
                    [open_trade_row(1)], [],
                    [], [],
                ]

                state = make_state()
                asyncio.run(state._reload_trades())
                state.confirm_delete(1)
                assert state.show_delete_confirm is True

                asyncio.run(state.execute_delete())

        persistence.delete_trade.assert_called_once()
        assert state.show_delete_confirm is False
        assert state.open_trades == []


@pytest.mark.integration
class TestPerformanceAndPreview:
    def test_performance_computed_from_closed_trades(self):
        with patch("phinan.services.services"):
            with patch("phinan.modules.options.workflow.persistence") as persistence:
                persistence.list_trades.side_effect = [
                    [],
                    [closed_trade_row(1, 240.0), closed_trade_row(2, -100.0)],
                ]

                state = make_state()
                asyncio.run(state._reload_trades())

        assert state.performance["trade_count"] == 2
        assert state.performance["win_rate"] == pytest.approx(0.5)
        assert state.performance["total_pnl"] == pytest.approx(140.0)

    def test_chain_row_prefills_form_and_preview(self):
        state = make_state()
        state.chain_ticker = "AAPL"
        state.chain_spot = 190.0
        state.chain_expiration = "2026-09-18"
        state.form_position_type = "long"

        state.select_chain_row(
            {"strike": 185.0, "mid": 3.55, "iv": 0.32}, "call"
        )

        assert state.form_ticker == "AAPL"
        assert state.form_strike == "185"
        assert state.form_premium == "3.55"
        assert state.form_strategy == "long_call"
        assert state.preview["break_even"] == pytest.approx(188.55)
        assert state.preview["max_loss"] == pytest.approx(355.0)
        assert state.preview["unlimited_profit"] is True

    def test_preview_recomputes_on_form_edit(self):
        state = make_state()
        fill_valid_form(state)
        state.form_iv = "30"

        state.set_form_field("premium", "4.00")

        assert state.preview["break_even"] == pytest.approx(189.0)
        assert state.preview["greeks"] is not None

    def test_short_position_derives_strategy(self):
        state = make_state()
        fill_valid_form(state)

        state.set_form_field("position_type", "short")

        assert state.form_strategy == "covered_call"


@pytest.mark.integration
class TestPatternAnalysis:
    def test_analysis_stores_result(self):
        with patch("phinan.services.services") as services:
            services.synthesis.health_check.return_value = True
            services.synthesis.generate_from_prompt.return_value = MagicMock(
                success=True, content="You lose on long puts."
            )

            async def run_test():
                state = await make_state_with_tree("pattern-ok-test")
                state.performance = {"trade_count": 6, "win_rate": 0.5}
                state.closed_trades = [closed_trade_row(i, 100.0) for i in range(6)]
                await exhaust(state.analyze_patterns())
                return state

            state = asyncio.run(run_test())

        assert state.pattern_analysis == "You lose on long puts."
        assert state.pattern_error == ""
        assert state.is_analyzing_patterns is False

    def test_unhealthy_llm_sets_error_only(self):
        with patch("phinan.services.services") as services:
            services.synthesis.health_check.return_value = False

            state = make_state()
            asyncio.run(exhaust(state.analyze_patterns()))

        assert state.pattern_analysis == ""
        assert "offline" in state.pattern_error

    def test_failure_is_isolated(self):
        with patch("phinan.services.services") as services:
            services.synthesis.health_check.return_value = True
            services.synthesis.generate_from_prompt.return_value = MagicMock(
                success=False, content="", error="boom"
            )

            state = make_state()
            state.performance = {"trade_count": 6}
            asyncio.run(exhaust(state.analyze_patterns()))

        assert "try again" in state.pattern_error
        assert state.is_analyzing_patterns is False
