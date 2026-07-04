"""Tests for persisted user-context field dispatch."""

from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestUserContextPersistence:
    @pytest.mark.asyncio
    async def test_load_context_dispatches_all_persisted_field_types(self):
        from phinan.state.user_context import UserContextState
        from reflex.istate.manager.memory import StateManagerMemory

        manager = StateManagerMemory.create(UserContextState.get_root_state())
        root = await manager.get_state("user-context-dispatch")
        state = root.get_substate(UserContextState.get_full_name().split("."))
        rows = [
            {"key": "active_profile", "value": "aggressive"},
            {"key": "risk_tolerance", "value": "aggressive"},
            {"key": "typical_strategy", "value": "directional"},
            {"key": "typical_timeframe", "value": "1_2_months"},
            {"key": "default_range_period", "value": "6mo"},
            {"key": "dark_mode", "value": "true"},
            {"key": "watchlist", "value": '["AAPL", "MSFT"]'},
            {"key": "avoid_list", "value": '["TSLA"]'},
            {"key": "future_field", "value": "ignored"},
        ]

        with patch("phinan.services.services") as services:
            services.db.query.return_value = rows
            await state.load_context()

        assert state.active_profile == "aggressive"
        assert state.risk_tolerance == "aggressive"
        assert state.typical_strategy == "directional"
        assert state.typical_timeframe == "1_2_months"
        assert state.default_range_period == "6mo"
        assert state.dark_mode is True
        assert state.watchlist == ["AAPL", "MSFT"]
        assert state.avoid_list == ["TSLA"]
        assert state._loaded is True

    @pytest.mark.asyncio
    async def test_malformed_value_does_not_block_other_fields(self):
        from phinan.state.user_context import UserContextState
        from reflex.istate.manager.memory import StateManagerMemory

        manager = StateManagerMemory.create(UserContextState.get_root_state())
        root = await manager.get_state("user-context-malformed")
        state = root.get_substate(UserContextState.get_full_name().split("."))
        rows = [
            {"key": "watchlist", "value": "[not valid json"},
            {"key": "active_profile", "value": "aggressive"},
            {"key": "avoid_list", "value": '["TSLA"]'},
        ]

        with patch("phinan.services.services") as services:
            services.db.query.return_value = rows
            await state.load_context()

        # The malformed watchlist is skipped, but later rows still load.
        assert state.watchlist == []  # untouched default
        assert state.active_profile == "aggressive"
        assert state.avoid_list == ["TSLA"]
        assert state._loaded is True
