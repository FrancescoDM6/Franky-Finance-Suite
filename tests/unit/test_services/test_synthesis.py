from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def synthesis_service():
    from phinan.services.synthesis import SynthesisService

    service = SynthesisService()
    yield service


@pytest.fixture
def sample_research_context():
    from phinan.services.synthesis import ResearchContext

    return ResearchContext(
        ticker="AAPL",
        ticker_info={
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "current_price": 175.50,
            "pe_ratio": 28.5,
        },
        price_range={
            "period": "3mo",
            "high": 195.00,
            "low": 165.00,
            "current": 175.50,
            "percent_of_range": 0.35,
        },
        analyst_data={
            "rating": "buy",
            "target_price": 200.00,
            "num_analysts": 40,
        },
        quality_check={
            "overall": "Pass",
            "flags": [],
        },
        news_sentiment="Positive",
        profile_name="Standard",
        profile_description="Learning investor focused on understanding",
        timeframe="varies",
        default_range="3mo",
        portfolio_position=None,
        options_summary="",
        options_expiration="",
    )


@pytest.mark.unit
class TestSynthesisServiceContextHash:
    def test_context_hash_includes_ticker(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker = "MSFT"
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_includes_profile(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.profile_name = "Conservative"
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_includes_sentiment(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.news_sentiment = "Negative"
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_includes_news_context(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.news_context = "2026-05-12 | Reuters | New headline"
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_rounds_price(
        self, synthesis_service, sample_research_context
    ):
        sample_research_context.ticker_info["current_price"] = 175.50
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker_info["current_price"] = 175.99
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 == hash2

    def test_context_hash_changes_on_price_dollar_change(
        self, synthesis_service, sample_research_context
    ):
        sample_research_context.ticker_info["current_price"] = 175.00
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker_info["current_price"] = 176.00
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_stable_within_price_band(
        self, synthesis_service, sample_research_context
    ):
        # Sub-0.1% noise must not invalidate the cache
        sample_research_context.ticker_info["current_price"] = 175.50
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker_info["current_price"] = 175.60
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 == hash2

    def test_context_hash_changes_on_material_price_move(
        self, synthesis_service, sample_research_context
    ):
        # A ~2% intraday move must invalidate the cache
        sample_research_context.ticker_info["current_price"] = 175.50
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker_info["current_price"] = 178.90
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_price_band_is_relative_to_scale(
        self, synthesis_service, sample_research_context
    ):
        # Banding works at low price scales too (3 significant digits)
        sample_research_context.ticker_info["current_price"] = 3.456
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.ticker_info["current_price"] = 3.512
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_includes_options_expiration(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.options_expiration = "2025-02-21"
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_includes_position(
        self, synthesis_service, sample_research_context
    ):
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.portfolio_position = {
            "quantity": 100,
            "cost_basis": 150.00,
        }
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 != hash2

    def test_context_hash_rounds_position_cost_basis(
        self, synthesis_service, sample_research_context
    ):
        sample_research_context.portfolio_position = {
            "quantity": 100,
            "cost_basis": 150.00,
        }
        hash1 = synthesis_service._compute_context_hash(sample_research_context)

        sample_research_context.portfolio_position = {
            "quantity": 100,
            "cost_basis": 150.49,
        }
        hash2 = synthesis_service._compute_context_hash(sample_research_context)

        assert hash1 == hash2


@pytest.mark.unit
class TestSynthesisServiceHealthCheck:
    def test_health_check_returns_true_when_llm_available(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        synthesis_service._llm = mock_llm

        assert synthesis_service.health_check() is True

    def test_health_check_returns_false_when_llm_unavailable(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = False
        synthesis_service._llm = mock_llm

        assert synthesis_service.health_check() is False

    def test_health_check_returns_false_on_exception(self, synthesis_service):
        with patch.object(
            synthesis_service, "_get_llm", side_effect=Exception("Error")
        ):
            assert synthesis_service.health_check() is False


@pytest.mark.unit
class TestSynthesisServiceGenerate:
    def test_generate_returns_error_when_llm_unavailable(
        self, synthesis_service, sample_research_context
    ):
        with patch.object(synthesis_service, "health_check", return_value=False):
            result = synthesis_service.generate_research_synthesis(
                sample_research_context
            )

        assert result.success is False
        assert result.error == "LLM service unavailable"

    def test_generate_returns_cached_result(
        self, synthesis_service, sample_research_context
    ):
        with patch.object(synthesis_service, "health_check", return_value=True):
            with patch.object(
                synthesis_service,
                "_get_cached_synthesis",
                return_value="Cached synthesis content",
            ):
                result = synthesis_service.generate_research_synthesis(
                    sample_research_context
                )

        assert result.success is True
        assert result.content == "Cached synthesis content"
        assert result.cached is True

    def test_generate_bypasses_cache_on_force_refresh(
        self, synthesis_service, sample_research_context
    ):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.return_value = "Fresh synthesis"
        synthesis_service._llm = mock_llm

        with patch.object(synthesis_service, "_cache_synthesis"):
            with patch(
                "phinan.services.synthesis.build_analysis_prompt", return_value="prompt"
            ):
                result = synthesis_service.generate_research_synthesis(
                    sample_research_context, force_refresh=True
                )

        assert result.success is True
        assert result.content == "Fresh synthesis"
        assert result.cached is False

    def test_generate_caches_fresh_result(
        self, synthesis_service, sample_research_context
    ):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.return_value = "Generated synthesis"
        synthesis_service._llm = mock_llm

        with patch.object(
            synthesis_service, "_get_cached_synthesis", return_value=None
        ):
            with patch.object(synthesis_service, "_cache_synthesis") as mock_cache:
                with patch(
                    "phinan.services.synthesis.build_analysis_prompt",
                    return_value="prompt",
                ):
                    result = synthesis_service.generate_research_synthesis(
                        sample_research_context
                    )

        mock_cache.assert_called_once()
        assert result.success is True
        assert result.cached is False

    def test_generate_handles_llm_exception(
        self, synthesis_service, sample_research_context
    ):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.side_effect = Exception("LLM error")
        synthesis_service._llm = mock_llm

        with patch.object(
            synthesis_service, "_get_cached_synthesis", return_value=None
        ):
            with patch(
                "phinan.services.synthesis.build_analysis_prompt", return_value="prompt"
            ):
                result = synthesis_service.generate_research_synthesis(
                    sample_research_context
                )

        assert result.success is False
        assert "LLM error" in result.error


@pytest.mark.unit
class TestSynthesisServiceFromPrompt:
    def test_generate_from_prompt_success(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.return_value = "Custom prompt response"
        synthesis_service._llm = mock_llm

        result = synthesis_service.generate_from_prompt("Custom prompt")

        assert result.success is True
        assert result.content == "Custom prompt response"

    def test_generate_from_prompt_error_when_unavailable(self, synthesis_service):
        with patch.object(synthesis_service, "health_check", return_value=False):
            result = synthesis_service.generate_from_prompt("Custom prompt")

        assert result.success is False
        assert "LLM service unavailable" in result.error

    def test_generate_from_prompt_handles_exception(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.side_effect = Exception("API error")
        synthesis_service._llm = mock_llm

        result = synthesis_service.generate_from_prompt("Custom prompt")

        assert result.success is False
        assert "API error" in result.error


@pytest.mark.unit
class TestSynthesisServiceCaching:
    def test_get_cached_synthesis_returns_none_on_miss(self, synthesis_service):
        with patch("phinan.core.database.get_database_manager") as mock_db:
            mock_db.return_value.query.return_value = []

            result = synthesis_service._get_cached_synthesis(
                "AAPL", "synthesis_full", "abc123"
            )

        assert result is None

    def test_get_cached_synthesis_returns_content_on_hit(self, synthesis_service):
        import json

        cached_data = {"content": "Cached content", "context_hash": "abc123"}

        with patch("phinan.core.database.get_database_manager") as mock_db:
            mock_db.return_value.query.return_value = [
                {"data": json.dumps(cached_data)}
            ]

            result = synthesis_service._get_cached_synthesis(
                "AAPL", "synthesis_full", "abc123"
            )

        assert result == "Cached content"

    def test_get_cached_synthesis_returns_none_on_hash_mismatch(
        self, synthesis_service
    ):
        import json

        cached_data = {"content": "Old content", "context_hash": "different_hash"}

        with patch("phinan.core.database.get_database_manager") as mock_db:
            mock_db.return_value.query.return_value = [
                {"data": json.dumps(cached_data)}
            ]

            result = synthesis_service._get_cached_synthesis(
                "AAPL", "synthesis_full", "abc123"
            )

        assert result is None

    def test_get_cached_synthesis_handles_db_error(self, synthesis_service):
        with patch("phinan.core.database.get_database_manager") as mock_db:
            mock_db.return_value.query.side_effect = Exception("DB error")

            result = synthesis_service._get_cached_synthesis(
                "AAPL", "synthesis_full", "abc123"
            )

        assert result is None

    def test_cache_synthesis_calls_db_execute(self, synthesis_service):
        with patch("phinan.core.database.get_database_manager") as mock_db:
            synthesis_service._cache_synthesis(
                "AAPL", "synthesis_full", "Test content", "abc123"
            )

        mock_db.return_value.execute.assert_called_once()

    def test_cache_synthesis_handles_db_error_gracefully(self, synthesis_service):
        with patch("phinan.core.database.get_database_manager") as mock_db:
            mock_db.return_value.execute.side_effect = Exception("DB error")

            synthesis_service._cache_synthesis(
                "AAPL", "synthesis_full", "Test content", "abc123"
            )


@pytest.mark.unit
class TestSynthesisServiceBankRecommendation:
    def test_evaluate_bank_recommendation_success(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.return_value = "Bank rec evaluation"
        synthesis_service._llm = mock_llm

        with patch(
            "phinan.services.synthesis.build_bank_rec_prompt", return_value="prompt"
        ):
            result = synthesis_service.evaluate_bank_recommendation(
                bank_recommendation="Buy AAPL target $200",
                ticker="AAPL",
                ticker_info={"current_price": 175},
                price_range={"high": 195, "low": 165},
                analyst_data={"target_price": 200},
                quality_check={"overall": "Pass"},
                news_sentiment="Positive",
                strategy_type="dividend_growth",
            )

        assert result.success is True
        assert result.content == "Bank rec evaluation"

    def test_evaluate_bank_recommendation_error_when_unavailable(
        self, synthesis_service
    ):
        with patch.object(synthesis_service, "health_check", return_value=False):
            result = synthesis_service.evaluate_bank_recommendation(
                bank_recommendation="Buy",
                ticker="AAPL",
                ticker_info={},
                price_range={},
                analyst_data={},
                quality_check={},
                news_sentiment="",
                strategy_type="",
            )

        assert result.success is False


@pytest.mark.unit
class TestSynthesisServiceThemeResearch:
    def test_research_theme_success(self, synthesis_service):
        mock_llm = MagicMock()
        mock_llm.health_check.return_value = True
        mock_llm.complete.return_value = "Theme research results"
        synthesis_service._llm = mock_llm

        with patch(
            "phinan.services.synthesis.build_theme_prompt", return_value="prompt"
        ):
            result = synthesis_service.research_theme(
                theme="AI stocks",
                tax_notes="Long-term capital gains preferred",
                risk_tolerance="moderate",
                margin_rate=6.5,
                strategy_type="growth",
                timeframe="1-3 years",
            )

        assert result.success is True
        assert result.content == "Theme research results"

    def test_research_theme_error_when_unavailable(self, synthesis_service):
        with patch.object(synthesis_service, "health_check", return_value=False):
            result = synthesis_service.research_theme(
                theme="",
                tax_notes="",
                risk_tolerance="",
                margin_rate=0,
                strategy_type="",
                timeframe="",
            )

        assert result.success is False
