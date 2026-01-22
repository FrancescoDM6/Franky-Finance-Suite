"""Unit tests for the TF-IDF + LR SentimentService."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for sentiment service."""
    with patch("phinan.services.sentiment.settings") as mock_settings:
        mock_settings.ai_services.enable_sentiment = True
        yield mock_settings


@pytest.fixture
def sentiment_service(mock_settings):
    """Create sentiment service with mocked dependencies."""
    from phinan.services.sentiment import SentimentService
    
    mock_llm = MagicMock()
    service = SentimentService(llm_service=mock_llm)
    return service


@pytest.fixture
def disabled_sentiment_service():
    """Create disabled sentiment service."""
    with patch("phinan.services.sentiment.settings") as mock_settings:
        mock_settings.ai_services.enable_sentiment = False
        
        from phinan.services.sentiment import SentimentService
        service = SentimentService()
        yield service


@pytest.mark.unit
class TestSentimentServiceHealthCheck:
    def test_health_check_returns_true_when_model_loaded(self, sentiment_service):
        # Mock successful model load
        with patch("phinan.services.sentiment._GLOBAL_MODEL", MagicMock()), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            assert sentiment_service.health_check() is True

    def test_health_check_returns_true_with_llm_fallback(self, mock_settings):
        from phinan.services.sentiment import SentimentService
        
        mock_llm = MagicMock()
        service = SentimentService(llm_service=mock_llm)
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", None), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            assert service.health_check() is True

    def test_health_check_returns_false_when_nothing_available(self, mock_settings):
        from phinan.services.sentiment import SentimentService
        
        service = SentimentService(llm_service=None)
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", None), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            assert service.health_check() is False


@pytest.mark.unit
class TestSentimentServiceScoreBatch:
    def test_score_batch_returns_empty_for_empty_input(self, sentiment_service):
        result = sentiment_service.score_batch([])
        assert result == []

    def test_score_batch_uses_local_model_for_high_confidence(self, sentiment_service):
        mock_model = MagicMock()
        mock_model.predict.return_value = [2]  # positive
        mock_model.predict_proba.return_value = [[0.05, 0.1, 0.85]]  # high confidence
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", mock_model), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            result = sentiment_service.score_batch(["Great earnings beat expectations"])
            
            assert result[0]["label"] == "positive"
            assert result[0]["score"] == 0.85
            assert result[0]["source"] == "local"

    def test_score_batch_uses_llm_for_low_confidence(self, mock_settings):
        from phinan.services.sentiment import SentimentService
        
        mock_llm = MagicMock()
        mock_llm.complete.return_value = '{"label": "positive", "score": 0.9, "reasoning": "test"}'
        
        service = SentimentService(llm_service=mock_llm)
        
        mock_model = MagicMock()
        mock_model.predict.return_value = [1]  # neutral
        mock_model.predict_proba.return_value = [[0.3, 0.49, 0.2]]  # low confidence (< 0.5)
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", mock_model), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            result = service.score_batch(["Ambiguous news headline"])
            
            assert result[0]["label"] == "positive"
            assert result[0]["source"] == "llm"
            assert "local_original" in result[0]

    def test_score_batch_returns_neutral_when_no_model(self, mock_settings):
        from phinan.services.sentiment import SentimentService
        
        service = SentimentService(llm_service=None)
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", None), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            result = service.score_batch(["Some headline"])
            
            assert result[0]["label"] == "neutral"
            assert "error" in result[0]


@pytest.mark.unit
class TestSentimentServiceScore:
    def test_score_single_text(self, sentiment_service):
        mock_model = MagicMock()
        mock_model.predict.return_value = [0]  # negative
        mock_model.predict_proba.return_value = [[0.88, 0.08, 0.04]]
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", mock_model), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", True):
            result = sentiment_service.score("Stock plunges on bad news")
            
            assert result["label"] == "negative"
            assert result["score"] == 0.88


@pytest.mark.unit
class TestSentimentServiceAggregate:
    def test_aggregate_calculates_counts(self, sentiment_service):
        with patch.object(sentiment_service, "score_batch") as mock_batch:
            mock_batch.return_value = [
                {"label": "positive", "score": 0.9},
                {"label": "positive", "score": 0.85},
                {"label": "negative", "score": 0.7},
                {"label": "neutral", "score": 0.6},
            ]
            
            result = sentiment_service.aggregate(["t1", "t2", "t3", "t4"])
        
        assert result["counts"]["positive"] == 2
        assert result["counts"]["negative"] == 1
        assert result["counts"]["neutral"] == 1
        assert result["dominant"] == "positive"
        assert result["total"] == 4

    def test_aggregate_handles_empty_input(self, sentiment_service):
        result = sentiment_service.aggregate([])
        
        assert result["total"] == 0
        assert result["average_score"] == 0.5


@pytest.mark.unit
class TestSentimentServiceModelLoading:
    def test_load_model_skips_when_disabled(self, disabled_sentiment_service):
        with patch("phinan.services.sentiment._GLOBAL_MODEL", None) as mock_global, \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", False):
            disabled_sentiment_service._load_model()
            
            # Should not change
            from phinan.services.sentiment import _GLOBAL_MODEL
            assert _GLOBAL_MODEL is None

    def test_load_model_handles_missing_file(self, mock_settings, tmp_path):
        from phinan.services.sentiment import SentimentService
        
        service = SentimentService()
        service._model_path = tmp_path / "nonexistent.joblib"
        
        with patch("phinan.services.sentiment._GLOBAL_MODEL", None), \
             patch("phinan.services.sentiment._GLOBAL_MODEL_LOADED", False):
            service._load_model()
            
            # _GLOBAL_MODEL_LOADED should become True, but model remains None
            from phinan.services.sentiment import _GLOBAL_MODEL, _GLOBAL_MODEL_LOADED
            assert _GLOBAL_MODEL is None
            assert _GLOBAL_MODEL_LOADED is True
