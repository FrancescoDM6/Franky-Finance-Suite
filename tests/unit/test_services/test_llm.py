from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def llm_service():
    with patch("phinan.services.llm.settings") as mock_settings:
        mock_settings.gemini.api_key = "test-key"
        mock_settings.gemini.model = "gemini-2.0-flash-exp"
        mock_settings.ollama.base_url = "http://localhost:11434"
        mock_settings.ollama.model = "llama3.2:latest"
        mock_settings.ollama.timeout = 120

        from phinan.services.llm import LLMService

        service = LLMService()
        yield service


class TestLLMServiceRateLimitParsing:
    def test_parse_daily_rate_limit(self, llm_service):
        error_daily = "429 RESOURCE_EXHAUSTED: Quota exceeded for RequestsPerDay"
        assert llm_service._parse_rate_limit_type(error_daily) == "daily"

    def test_parse_minute_rate_limit(self, llm_service):
        error_minute = "429 RESOURCE_EXHAUSTED: Quota exceeded for RequestsPerMinute"
        assert llm_service._parse_rate_limit_type(error_minute) == "minute"

    def test_parse_token_rate_limit(self, llm_service):
        error_tokens = "429 RESOURCE_EXHAUSTED: Token limit exceeded"
        assert llm_service._parse_rate_limit_type(error_tokens) == "tokens"

    def test_parse_unknown_rate_limit(self, llm_service):
        error_unknown = "429 RESOURCE_EXHAUSTED: Some other error"
        assert llm_service._parse_rate_limit_type(error_unknown) == "unknown"


class TestLLMServiceGeminiChat:
    def test_chat_gemini_success(self, llm_service):
        mock_response = MagicMock()
        mock_response.text = "Test response"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        llm_service._gemini_client = mock_client
        llm_service._use_gemini = True

        result = llm_service.chat([{"role": "user", "content": "Hello"}])

        assert result["content"] == "Test response"
        assert "model" in result

    def test_chat_gemini_falls_back_on_rate_limit(self, llm_service):
        mock_gemini = MagicMock()
        mock_gemini.models.generate_content.side_effect = Exception(
            "429 RESOURCE_EXHAUSTED"
        )
        llm_service._gemini_client = mock_gemini
        llm_service._use_gemini = True

        mock_ollama = MagicMock()
        mock_ollama.chat.return_value = {"message": {"content": "Fallback response"}}
        llm_service._ollama_client = mock_ollama

        with patch("phinan.services.llm.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value.allow_request.return_value = True
            mock_breaker.return_value.record_success = MagicMock()

            with patch("phinan.services.llm.with_timeout") as mock_timeout:
                mock_timeout.return_value = {
                    "message": {"content": "Fallback response"}
                }
                result = llm_service.chat([{"role": "user", "content": "Hello"}])

        assert result["content"] == "Fallback response"

    def test_chat_marks_model_exhausted_on_daily_limit(self, llm_service):
        mock_gemini = MagicMock()
        mock_gemini.models.generate_content.side_effect = Exception(
            "429 RESOURCE_EXHAUSTED: Quota exceeded for RequestsPerDay"
        )
        llm_service._gemini_client = mock_gemini
        llm_service._use_gemini = True
        llm_service._daily_exhausted_models = set()

        mock_ollama = MagicMock()
        mock_ollama.chat.return_value = {"message": {"content": "Fallback"}}
        llm_service._ollama_client = mock_ollama

        with patch("phinan.services.llm.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value.allow_request.return_value = True
            mock_breaker.return_value.record_success = MagicMock()

            llm_service.chat([{"role": "user", "content": "Hello"}])

        assert llm_service._gemini_model_name in llm_service._daily_exhausted_models


class TestLLMServiceOllamaChat:
    def test_chat_ollama_success(self, llm_service):
        mock_ollama = MagicMock()
        mock_ollama.chat.return_value = {"message": {"content": "Ollama response"}}
        llm_service._ollama_client = mock_ollama
        llm_service._use_gemini = False

        with patch("phinan.services.llm.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value.allow_request.return_value = True
            mock_breaker.return_value.record_success = MagicMock()

            with patch("phinan.services.llm.with_timeout") as mock_timeout:
                mock_timeout.return_value = {"message": {"content": "Ollama response"}}
                result = llm_service.chat([{"role": "user", "content": "Hello"}])

        assert result["content"] == "Ollama response"

    def test_chat_ollama_circuit_open_returns_error(self, llm_service):
        llm_service._use_gemini = False

        with patch("phinan.services.llm.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value.allow_request.return_value = False

            result = llm_service._chat_ollama([{"role": "user", "content": "Hello"}])

        assert result.get("error") is True
        assert result.get("circuit_open") is True

    def test_chat_ollama_timeout_records_failure(self, llm_service):
        mock_ollama = MagicMock()
        llm_service._ollama_client = mock_ollama
        llm_service._use_gemini = False

        with patch("phinan.services.llm.get_circuit_breaker") as mock_breaker:
            mock_breaker.return_value.allow_request.return_value = True
            mock_breaker.return_value.record_failure = MagicMock()

            with patch("phinan.services.llm.with_timeout") as mock_timeout:
                mock_timeout.side_effect = TimeoutError("Timed out")

                result = llm_service._chat_ollama(
                    [{"role": "user", "content": "Hello"}]
                )

        assert result.get("error") is True
        assert result.get("timeout") is True
        mock_breaker.return_value.record_failure.assert_called_once()


class TestLLMServiceComplete:
    def test_complete_wraps_chat(self, llm_service):
        with patch.object(llm_service, "chat") as mock_chat:
            mock_chat.return_value = {"content": "Completion result"}

            result = llm_service.complete("Test prompt")

        assert result == "Completion result"
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args
        assert call_args[1]["messages"][0]["content"] == "Test prompt"


class TestLLMServiceHealthCheck:
    def test_health_check_gemini_available(self, llm_service):
        llm_service._use_gemini = True
        llm_service._gemini_client = MagicMock()

        assert llm_service.health_check() is True

    def test_health_check_falls_back_to_ollama(self, llm_service):
        llm_service._use_gemini = False

        mock_ollama = MagicMock()
        mock_ollama.list.return_value = {"models": []}
        llm_service._ollama_client = mock_ollama

        assert llm_service.health_check() is True

    def test_health_check_returns_false_when_all_fail(self, llm_service):
        llm_service._use_gemini = False

        with patch.object(llm_service, "_get_ollama_client") as mock_get:
            mock_client = MagicMock()
            mock_client.list.side_effect = Exception("Connection failed")
            mock_get.return_value = mock_client

            assert llm_service.health_check() is False
