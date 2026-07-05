"""Integration tests for Research volatility state."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


async def _create_volatility_state(token: str):
    from phinan.modules.research.options_state import OptionsState
    from phinan.modules.research.state import ResearchState
    from phinan.modules.research.volatility_state import VolatilityState
    from reflex.istate.manager.memory import StateManagerMemory

    manager = StateManagerMemory.create(ResearchState.get_root_state())
    root = await manager.get_state(token)
    research_state = root.get_substate(ResearchState.get_full_name().split("."))
    await research_state.get_state(OptionsState)
    volatility_state = await research_state.get_state(VolatilityState)
    return research_state, volatility_state


@pytest.mark.integration
class TestVolatilityState:
    def test_requires_explicit_options_atm_iv(self):
        async def run_test():
            research_state, volatility_state = await _create_volatility_state(
                "missing-atm-test"
            )
            research_state.selected_ticker = "AAPL"
            await volatility_state._fetch_volatility_data(options_atm_iv=0.0)
            return volatility_state

        state = asyncio.run(run_test())

        assert state.volatility_available is False
        assert state.volatility_error == "ATM IV not available"

    def test_computes_from_explicit_options_snapshot(self):
        history = pd.DataFrame(
            {"Close": [100.0 + index for index in range(70)]}
        )
        result = MagicMock(
            garch_annualized_vol=0.22,
            implied_vol=0.30,
            iv_garch_ratio=1.36,
            iv_garch_diff=0.08,
            expected_range_low=94.0,
            expected_range_high=106.0,
        )

        with patch("phinan.services.services") as services:
            services.volatility.health_check.return_value = True
            services.market_data.get_price_history_async = AsyncMock(
                return_value=history
            )
            services.volatility.compare_to_implied_vol.return_value = result

            async def run_test():
                research_state, volatility_state = await _create_volatility_state(
                    "compute-test"
                )
                research_state.selected_ticker = "AAPL"
                research_state.ticker_info = {"current_price": 100.0}
                await volatility_state._fetch_volatility_data(options_atm_iv=0.30)
                return volatility_state

            state = asyncio.run(run_test())

        assert state.volatility_available is True
        assert state.volatility_implied_vol == 0.30
        services.volatility.compare_to_implied_vol.assert_called_once()
        assert (
            services.volatility.compare_to_implied_vol.call_args.kwargs[
                "implied_vol"
            ]
            == 0.30
        )

    def test_horizon_change_reads_options_sibling(self):
        from phinan.modules.research.options_state import OptionsState
        from phinan.modules.research.state import ResearchState
        from phinan.modules.research.volatility_state import VolatilityState
        from reflex.istate.manager.memory import StateManagerMemory

        async def change_horizon():
            manager = StateManagerMemory.create(ResearchState.get_root_state())
            root = await manager.get_state("horizon-test")
            state = root.get_substate(ResearchState.get_full_name().split("."))
            options_state = await state.get_state(OptionsState)
            volatility_state = await state.get_state(VolatilityState)
            options_state.options_atm_iv = 0.27

            with patch.object(
                VolatilityState,
                "_fetch_volatility_data",
                new_callable=AsyncMock,
            ) as fetch:
                await volatility_state.set_volatility_horizon("63")
                fetch.assert_awaited_once_with(0.27)

            return volatility_state

        state = asyncio.run(change_horizon())
        assert state.volatility_horizon == "63"
