import pytest

from phinan.modules.research.prompts import build_analysis_prompt
from phinan.pages.prompts import build_daily_brief_prompt


@pytest.mark.unit
class TestResearchPromptBuilder:
    def test_analysis_prompt_includes_date_freshness_and_profile_context(self):
        prompt = build_analysis_prompt(
            ticker="AAPL",
            ticker_info={"name": "Apple Inc.", "current_price": 175.5},
            price_range={"period": "3mo", "percent_of_range": 0.4},
            analyst_data={"rating": "buy", "target_price": 200},
            quality_check={"overall": "Pass", "flags": []},
            news_sentiment="Positive",
            profile_name="Conservative",
            profile_description="Options as entry and exit mechanism",
            timeframe="2_weeks",
            default_range="3mo",
            analysis_date="2026-05-12",
            data_freshness="Fetched by the app on 2026-05-12.",
            news_context="- 2026-05-12T09:00:00 | Reuters | Apple headline",
        )

        assert "Analysis Date: 2026-05-12" in prompt
        assert "Fetched by the app on 2026-05-12." in prompt
        assert "Typical timeframe: 2_weeks" in prompt
        assert "Reuters | Apple headline" in prompt
        assert "Strict Sourcing" in prompt
        assert "Choose outright shares, options, or cash/no action" in prompt
        assert "Do not force an options trade" in prompt

    def test_analysis_prompt_blocks_specific_options_when_missing(self):
        prompt = build_analysis_prompt(
            ticker="AAPL",
            ticker_info={"name": "Apple Inc.", "current_price": 175.5},
            price_range={"period": "3mo", "percent_of_range": 0.4},
            analyst_data={"rating": "buy", "target_price": 200},
            quality_check={"overall": "Pass", "flags": []},
            news_sentiment="Positive",
            profile_name="Conservative",
            profile_description="Options as entry and exit mechanism",
            timeframe="2_weeks",
            default_range="3mo",
            options_summary="",
            options_expiration="",
        )

        assert "No options data provided." in prompt
        assert "Do not recommend a specific option contract" in prompt
        assert "use the exact expiration dates shown above" not in prompt

    def test_analysis_prompt_allows_exact_options_when_provided(self):
        prompt = build_analysis_prompt(
            ticker="AAPL",
            ticker_info={"name": "Apple Inc.", "current_price": 175.5},
            price_range={"period": "3mo", "percent_of_range": 0.4},
            analyst_data={"rating": "buy", "target_price": 200},
            quality_check={"overall": "Pass", "flags": []},
            news_sentiment="Positive",
            profile_name="Conservative",
            profile_description="Options as entry and exit mechanism",
            timeframe="2_weeks",
            default_range="3mo",
            options_summary="Options for 2026-05-15 (3 days):\n  $180: $1.20 bid",
            options_expiration="2026-05-15",
        )

        assert "Options for 2026-05-15" in prompt
        assert "use the exact expiration dates shown above" in prompt
        assert "2026-05-15" in prompt


@pytest.mark.unit
class TestDailyBriefPromptBuilder:
    def test_daily_brief_prompt_includes_date_freshness_and_profile_context(self):
        prompt = build_daily_brief_prompt(
            profile_name="Conservative",
            profile_key="conservative",
            total_value=100000,
            total_pl_pct=4.2,
            position_count=2,
            position_summary="- AAPL: $50,000.00 (+2.0%)",
            movers_summary="- AAPL: +1.2% (gainer)",
            watchlist_summary="- MSFT: $420.00",
            news_summary="- [AAPL] 2026-05-12T09:00:00 | Reuters | Headline",
            analysis_date="2026-05-12",
            data_freshness="Brief data was assembled by the app on 2026-05-12.",
            timeframe="2_weeks",
            avoid_list="TSLA",
        )

        assert "Brief Date: 2026-05-12" in prompt
        assert "Brief data was assembled by the app on 2026-05-12." in prompt
        assert "Typical Timeframe: 2_weeks" in prompt
        assert "Avoid List: TSLA" in prompt
        assert "Reuters | Headline" in prompt
        assert "Strict Sourcing" in prompt
