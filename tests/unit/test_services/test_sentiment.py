from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sentiment_service():
    with patch("phinan.services.sentiment.settings") as mock_settings:
        mock_settings.ai_services.sentiment_model = "yiyanghkust/finbert-tone"
        mock_settings.ai_services.enable_sentiment = True
        mock_settings.ollama.base_url = "http://localhost:11434"
        mock_settings.ollama.model = "llama3.2:latest"
        mock_settings.ollama.timeout = 120

        with patch("phinan.services.sentiment.get_resource_monitor") as mock_monitor:
            mock_monitor.return_value.is_safe_to_run.return_value = True

            from phinan.services.sentiment import SentimentService

            service = SentimentService()
            yield service


@pytest.fixture
def disabled_sentiment_service():
    with patch("phinan.services.sentiment.settings") as mock_settings:
        mock_settings.ai_services.sentiment_model = "yiyanghkust/finbert-tone"
        mock_settings.ai_services.enable_sentiment = False

        with patch("phinan.services.sentiment.get_resource_monitor") as mock_monitor:
            mock_monitor.return_value.is_safe_to_run.return_value = True

            from phinan.services.sentiment import SentimentService

            service = SentimentService()
            yield service


@pytest.mark.unit
class TestSentimentServiceHealthCheck:
    def test_health_check_returns_true_when_enabled(self, sentiment_service):
        assert sentiment_service.health_check() is True

    def test_health_check_returns_false_when_disabled(self, disabled_sentiment_service):
        assert disabled_sentiment_service.health_check() is False


@pytest.mark.unit
class TestSentimentServiceScoreBatch:
    def test_score_batch_returns_empty_for_empty_input(self, sentiment_service):
        result = sentiment_service.score_batch([])

        assert result == []

    def test_score_batch_returns_neutral_when_disabled(
        self, disabled_sentiment_service
    ):
        result = disabled_sentiment_service.score_batch(["Test headline"])

        assert len(result) == 1
        assert result[0]["label"] == "neutral"
        assert result[0]["score"] == 0.5
        assert result[0]["enabled"] is False

    def test_score_batch_returns_neutral_when_model_not_loaded(self, sentiment_service):
        sentiment_service._model = None
        sentiment_service._enabled = True

        with patch.object(sentiment_service, "_load_model"):
            result = sentiment_service.score_batch(["Test headline"])

        assert len(result) == 1
        assert result[0]["label"] == "neutral"
        assert "error" in result[0]

    def test_score_batch_uses_finbert_for_high_confidence(self, sentiment_service):
        mock_finbert_result = [{"label": "positive", "score": 0.95}]

        with patch.object(
            sentiment_service, "_score_finbert_batch", return_value=mock_finbert_result
        ):
            sentiment_service._model = MagicMock()
            result = sentiment_service.score_batch(["Great earnings report"])

        assert result[0]["label"] == "positive"
        assert result[0]["source"] == "finbert"

    def test_score_batch_uses_llm_for_low_confidence(self, sentiment_service):
        mock_finbert_result = [{"label": "neutral", "score": 0.6}]
        mock_llm_result = {"label": "positive", "score": 0.85, "source": "llm"}

        mock_llm_provider = MagicMock()
        mock_llm_provider.score_sentiment.return_value = mock_llm_result

        with patch.object(
            sentiment_service, "_score_finbert_batch", return_value=mock_finbert_result
        ):
            with patch.object(
                sentiment_service, "_get_llm_provider", return_value=mock_llm_provider
            ):
                sentiment_service._model = MagicMock()
                sentiment_service._llm_enabled = True
                result = sentiment_service.score_batch(["Mixed news about company"])

        assert result[0]["label"] == "positive"
        assert result[0]["source"] == "llm"
        assert "finbert_original" in result[0]


@pytest.mark.unit
class TestSentimentServiceScore:
    def test_score_single_text(self, sentiment_service):
        mock_batch_result = [{"label": "negative", "score": 0.88, "source": "finbert"}]

        with patch.object(
            sentiment_service, "score_batch", return_value=mock_batch_result
        ):
            result = sentiment_service.score("Stock plunges on bad news")

        assert result["label"] == "negative"
        assert result["score"] == 0.88

    def test_score_returns_neutral_on_empty_batch(self, sentiment_service):
        with patch.object(sentiment_service, "score_batch", return_value=[]):
            result = sentiment_service.score("Test text")

        assert result["label"] == "neutral"
        assert result["score"] == 0.5


@pytest.mark.unit
class TestSentimentServiceAggregate:
    def test_aggregate_calculates_counts(self, sentiment_service):
        mock_scores = [
            {"label": "positive", "score": 0.9},
            {"label": "positive", "score": 0.85},
            {"label": "negative", "score": 0.7},
            {"label": "neutral", "score": 0.6},
        ]

        with patch.object(sentiment_service, "score_batch", return_value=mock_scores):
            result = sentiment_service.aggregate(["t1", "t2", "t3", "t4"])

        assert result["counts"]["positive"] == 2
        assert result["counts"]["negative"] == 1
        assert result["counts"]["neutral"] == 1
        assert result["dominant"] == "positive"
        assert result["total"] == 4

    def test_aggregate_calculates_average_score(self, sentiment_service):
        mock_scores = [
            {"label": "positive", "score": 0.8},
            {"label": "positive", "score": 0.9},
        ]

        with patch.object(sentiment_service, "score_batch", return_value=mock_scores):
            result = sentiment_service.aggregate(["t1", "t2"])

        assert abs(result["average_score"] - 0.85) < 0.001

    def test_aggregate_handles_empty_input(self, sentiment_service):
        with patch.object(sentiment_service, "score_batch", return_value=[]):
            result = sentiment_service.aggregate([])

        assert result["total"] == 0
        assert result["average_score"] == 0.5


@pytest.mark.unit
class TestOllamaSentimentProvider:
    def test_score_sentiment_parses_json_response(self):
        from phinan.services.sentiment import OllamaSentimentProvider

        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            mock_settings.ollama.model = "llama3.2:latest"
            mock_settings.ollama.timeout = 120

            provider = OllamaSentimentProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"label": "positive", "score": 0.85, "reasoning": "Strong earnings"}'
        }

        with patch("httpx.post", return_value=mock_response):
            result = provider.score_sentiment("Company beats earnings expectations")

        assert result["label"] == "positive"
        assert result["score"] == 0.85
        assert result["source"] == "llm"

    def test_score_sentiment_handles_markdown_json(self):
        from phinan.services.sentiment import OllamaSentimentProvider

        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            mock_settings.ollama.model = "llama3.2:latest"
            mock_settings.ollama.timeout = 120

            provider = OllamaSentimentProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '```json\n{"label": "negative", "score": 0.75}\n```'
        }

        with patch("httpx.post", return_value=mock_response):
            result = provider.score_sentiment("Stock drops on weak guidance")

        assert result["label"] == "negative"
        assert result["score"] == 0.75

    def test_score_sentiment_handles_invalid_json(self):
        from phinan.services.sentiment import OllamaSentimentProvider

        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            mock_settings.ollama.model = "llama3.2:latest"
            mock_settings.ollama.timeout = 120

            provider = OllamaSentimentProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is not valid JSON"}

        with patch("httpx.post", return_value=mock_response):
            result = provider.score_sentiment("Test headline")

        assert result["label"] == "neutral"
        assert result["score"] == 0.5
        assert "error" in result

    def test_score_sentiment_handles_http_error(self):
        from phinan.services.sentiment import OllamaSentimentProvider

        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            mock_settings.ollama.model = "llama3.2:latest"
            mock_settings.ollama.timeout = 120

            provider = OllamaSentimentProvider()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.post", return_value=mock_response):
            result = provider.score_sentiment("Test headline")

        assert result["label"] == "neutral"
        assert result["error"] == "http_500"

    def test_score_sentiment_handles_connection_error(self):
        from phinan.services.sentiment import OllamaSentimentProvider

        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            mock_settings.ollama.model = "llama3.2:latest"
            mock_settings.ollama.timeout = 120

            provider = OllamaSentimentProvider()

        with patch("httpx.post", side_effect=Exception("Connection refused")):
            result = provider.score_sentiment("Test headline")

        assert result["label"] == "neutral"
        assert "Connection refused" in result["error"]


@pytest.mark.unit
class TestSentimentServiceModelLoading:
    def test_load_model_skips_when_disabled(self):
        with patch("phinan.services.sentiment.settings") as mock_settings:
            mock_settings.ai_services.sentiment_model = "yiyanghkust/finbert-tone"
            mock_settings.ai_services.enable_sentiment = False

            with patch(
                "phinan.services.sentiment.get_resource_monitor"
            ) as mock_monitor:
                mock_monitor.return_value.is_safe_to_run.return_value = True

                from phinan.services.sentiment import SentimentService

                service = SentimentService()
                service._load_model()

        assert service._model is None

    def test_load_model_skips_on_insufficient_resources(self, sentiment_service):
        sentiment_service._resource_monitor.is_safe_to_run.return_value = False
        sentiment_service._model = None

        sentiment_service._load_model()

        assert sentiment_service._model is None
        assert sentiment_service._enabled is False
