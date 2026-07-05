"""State-manager integration tests for the Research state hierarchy."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _create_state_tree(token: str):
    from phinan.modules.research.options_state import OptionsState
    from phinan.modules.research.state import ResearchState
    from phinan.modules.research.volatility_state import VolatilityState
    from phinan.modules.portfolio.state import PortfolioState
    from phinan.state.user_context import UserContextState
    from reflex.istate.manager.memory import StateManagerMemory

    manager = StateManagerMemory.create(ResearchState.get_root_state())
    root = await manager.get_state(token)
    research_state = root.get_substate(ResearchState.get_full_name().split("."))
    options_state = await research_state.get_state(OptionsState)
    volatility_state = await research_state.get_state(VolatilityState)
    await research_state.get_state(UserContextState)
    await research_state.get_state(PortfolioState)
    return root, research_state, options_state, volatility_state


@pytest.mark.integration
class TestResearchStateCoordination:
    def test_children_share_inherited_research_state(self):
        async def run_test():
            return await _create_state_tree("shared-parent-test")

        _, research_state, options_state, volatility_state = (
            asyncio.run(run_test())
        )
        research_state.selected_ticker = "AAPL"
        research_state.ticker_info = {"current_price": 200.0}

        assert options_state.selected_ticker == "AAPL"
        assert volatility_state.selected_ticker == "AAPL"
        assert options_state.ticker_info["current_price"] == 200.0
        assert volatility_state.ticker_info["current_price"] == 200.0

    def test_one_root_delta_contains_parent_and_child_updates(self):
        from phinan.modules.research.options_state import OptionsState
        from phinan.modules.research.state import ResearchState
        from phinan.modules.research.volatility_state import VolatilityState

        async def run_test():
            return await _create_state_tree("delta-test")

        root, research_state, options_state, volatility_state = (
            asyncio.run(run_test())
        )
        root._clean()

        research_state.loading_stage = "Loading Options & Charts..."
        options_state.options_summary = "Options snapshot"
        volatility_state.volatility_error = "ATM IV not available"

        delta = root.get_delta()

        assert ResearchState.get_full_name() in delta
        assert OptionsState.get_full_name() in delta
        assert VolatilityState.get_full_name() in delta
        research_delta = delta[ResearchState.get_full_name()]
        options_delta = delta[OptionsState.get_full_name()]
        volatility_delta = delta[VolatilityState.get_full_name()]

        assert next(
            value
            for key, value in research_delta.items()
            if key.startswith("loading_stage")
        ) == "Loading Options & Charts..."
        assert next(
            value
            for key, value in options_delta.items()
            if key.startswith("options_summary")
        ) == "Options snapshot"
        assert next(
            value
            for key, value in volatility_delta.items()
            if key.startswith("volatility_error")
        ) == "ATM IV not available"

    def test_synthesis_receives_explicit_options_snapshot(self):
        async def run_test():
            _, research_state, options_state, _ = await _create_state_tree(
                "synthesis-options-test"
            )
            research_state.selected_ticker = "AAPL"
            research_state.ticker_info = {"current_price": 200.0}
            research_state.price_range = {"high": 210.0, "low": 180.0}
            options_state.options_summary = "Options snapshot"
            options_state.selected_expiration = "2026-07-17"

            synthesis_result = MagicMock(success=True, content="Analysis")
            with patch("phinan.services.services") as services:
                services.synthesis.health_check.return_value = True
                services.synthesis.generate_research_synthesis_async = AsyncMock(
                    return_value=synthesis_result
                )
                await research_state._generate_synthesis(
                    options_summary=options_state.options_summary,
                    options_expiration=options_state.selected_expiration,
                )

                context = services.synthesis.generate_research_synthesis_async.call_args.args[
                    0
                ]
                return research_state, context

        state, context = asyncio.run(run_test())

        assert state.llm_synthesis == "Analysis"
        assert context.options_summary == "Options snapshot"
        assert context.options_expiration == "2026-07-17"
