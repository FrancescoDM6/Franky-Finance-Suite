"""Integration tests for the dashboard daily brief workflow."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


async def _create_dashboard_state(token: str):
    from phinan.modules.dashboard.state import DailyBriefState
    from phinan.modules.portfolio.state import PortfolioState
    from phinan.state.user_context import UserContextState
    from reflex.istate.manager.memory import StateManagerMemory

    manager = StateManagerMemory.create(DailyBriefState.get_root_state())
    root = await manager.get_state(token)
    dashboard = root.get_substate(DailyBriefState.get_full_name().split("."))
    user_context = await dashboard.get_state(UserContextState)
    portfolio = await dashboard.get_state(PortfolioState)
    return dashboard, user_context, portfolio


async def _collect_stages(dashboard, event_generator) -> list[str]:
    stages = []
    async for _ in event_generator:
        stages.append(dashboard.loading_status)
    return stages


@pytest.mark.integration
class TestDailyBriefState:
    @pytest.mark.asyncio
    async def test_uses_brief_cached_for_current_date(self):
        dashboard, _, _ = await _create_dashboard_state("dashboard-cache")
        dashboard.brief_content = "Cached brief"
        dashboard._brief_date = datetime.now().strftime("%Y-%m-%d")

        with patch("phinan.services.services") as services:
            stages = await _collect_stages(dashboard, dashboard.generate_brief())

        assert stages == []
        assert dashboard.brief_content == "Cached brief"
        services.llm.health_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_daily_cache(self):
        dashboard, user_context, portfolio = await _create_dashboard_state(
            "dashboard-force-refresh"
        )
        dashboard.brief_content = "Cached brief"
        dashboard._brief_date = datetime.now().strftime("%Y-%m-%d")
        user_context.watchlist = []
        portfolio.positions = []

        with patch("phinan.services.services") as services:
            services.llm.health_check.return_value = True
            services.llm.complete_async = AsyncMock(return_value="Fresh brief")
            await _collect_stages(dashboard, dashboard.force_regenerate_brief())

        assert dashboard.brief_content == "Fresh brief"
        services.llm.health_check.assert_called_once_with()
        services.llm.complete_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_when_llm_is_unavailable(self):
        dashboard, user_context, portfolio = await _create_dashboard_state(
            "dashboard-fallback"
        )
        user_context.watchlist = []
        portfolio.positions = []

        with patch("phinan.services.services") as services:
            services.llm.health_check.return_value = False
            services.llm.complete_async = AsyncMock()
            await _collect_stages(dashboard, dashboard.generate_brief())

        assert "Good morning" in dashboard.brief_content
        assert "LLM unavailable" in dashboard.brief_content
        assert dashboard._brief_date == datetime.now().strftime("%Y-%m-%d")
        assert dashboard.brief_loading is False
        services.llm.complete_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_emits_loading_stages_in_order(self):
        dashboard, user_context, portfolio = await _create_dashboard_state(
            "dashboard-loading-stages"
        )
        user_context.watchlist = []
        portfolio.positions = []

        with patch("phinan.services.services") as services:
            services.llm.health_check.return_value = True
            services.llm.complete_async = AsyncMock(return_value="Generated brief")
            stages = await _collect_stages(dashboard, dashboard.generate_brief())

        assert stages == [
            "Initializing...",
            "Fetching portfolio data...",
            "Fetching watchlist data...",
            "Fetching news for holdings...",
            "Generating summary with AI...",
        ]
        assert dashboard.brief_loading is False

    @pytest.mark.asyncio
    async def test_exposes_generation_errors_to_the_ui(self):
        dashboard, user_context, portfolio = await _create_dashboard_state(
            "dashboard-error"
        )
        user_context.watchlist = []
        portfolio.positions = []

        with patch("phinan.services.services") as services:
            services.llm.health_check.return_value = True
            services.llm.complete_async = AsyncMock(
                side_effect=RuntimeError("backend failed")
            )
            await _collect_stages(dashboard, dashboard.generate_brief())

        assert dashboard.brief_error == "Error generating brief: backend failed"
        assert dashboard.brief_content == ""
        assert dashboard.brief_loading is False
