"""Google Gemini backend for the LLM service."""

import logging
from datetime import date, datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from ..model_cascade import ModelCascade, estimate_tokens, get_cost_tracker

logger = logging.getLogger(__name__)

OllamaFallback = Callable[
    [list[dict[str, str]], Optional[str], Optional[str], Optional[list[dict]]],
    dict[str, Any],
]


class GeminiBackend:
    """Gemini client, model cascade, quota tracking, and streaming."""

    def __init__(self, api_key: str, model_name: str):
        self._api_key = api_key
        self._model_name = model_name
        self._client = None
        self._daily_exhausted_models: set[str] = set()
        self._daily_exhausted_at: Optional[date] = None

    @property
    def model_name(self) -> str:
        """Return the configured default model name."""
        return self._model_name

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. Run: pip install google-genai"
                )
        return self._client

    def health_check(self) -> bool:
        """Check whether the Gemini client can be created."""
        try:
            self._get_client()
            return True
        except Exception:
            return False

    @staticmethod
    def model_for_task(task_type: str) -> str:
        """Select the configured cascade model for a task type."""
        return ModelCascade.get_model_for_task(task_type).name

    def chat(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        tools: Optional[list[dict]],
        task_type: Optional[str],
        cascade_model: Optional[str],
        ollama_fallback: OllamaFallback,
    ) -> dict[str, Any]:
        """Chat using Gemini with model fallback and Ollama fallback."""
        gemini_models = self._model_candidates(cascade_model)
        self._reset_daily_quota_state_if_needed()
        available_models = [
            model
            for model in gemini_models
            if model not in self._daily_exhausted_models
        ]

        if not available_models:
            logger.warning(
                "All Gemini models exhausted for the day; using Ollama fallback"
            )
            try:
                return ollama_fallback(messages, system, None, tools)
            except Exception:
                return {
                    "content": (
                        "AI analysis is temporarily unavailable - the daily API "
                        "quota has been reached. Please try again tomorrow, or "
                        "configure a local Ollama instance as a fallback."
                    ),
                    "error": True,
                }

        contents = self._build_contents(messages, system)
        last_error: Optional[Exception] = None

        for model_name in available_models:
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                self._record_cost(task_type, model_name, contents, response.text or "")
                logger.info(
                    "LLM response from %s (%d chars)",
                    model_name,
                    len(response.text or ""),
                )
                return {"content": response.text, "model": model_name}
            except Exception as e:
                last_error = e
                self._record_model_failure(model_name, e)

        logger.warning(
            "All %d Gemini models failed (tried: %s); using Ollama fallback",
            len(available_models),
            ", ".join(available_models),
        )

        ollama_result = None
        try:
            ollama_result = ollama_fallback(messages, system, None, tools)
        except Exception as e:
            logger.warning("Ollama fallback failed with exception: %s", e)

        if ollama_result and not ollama_result.get("error"):
            return ollama_result
        if ollama_result:
            logger.warning("Ollama fallback failed: %s", ollama_result.get("content"))

        last_error_text = str(last_error) if last_error else ""
        if "429" in last_error_text or "RESOURCE_EXHAUSTED" in last_error_text:
            user_message = (
                "AI analysis is temporarily unavailable - the API rate limit has "
                "been reached. Please wait a few minutes and try again."
            )
        else:
            user_message = (
                "AI analysis is temporarily unavailable. Please check your API "
                "configuration and try again."
            )
        return {"content": user_message, "error": True}

    def stream(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
    ):
        """Stream a Gemini response token by token."""
        try:
            client = self._get_client()
            contents = self._build_contents(messages, system)
            for chunk in client.models.generate_content_stream(
                model=self._model_name,
                contents=contents,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"Error: {str(e)}"

    def _model_candidates(self, cascade_model: Optional[str]) -> list[str]:
        if cascade_model:
            return [cascade_model]

        # Static GA flash-tier fallbacks, ordered most-capable -> most-available.
        # Kept in the flash tier on purpose: this cascade exists to stay available
        # when the primary model is rate-limited, not to escalate to Pro (which has
        # lower quota and higher cost). Update when these reach end-of-life; the
        # Gemini 2.0 models previously here were shut down on 2026-06-01.
        candidates = [
            self._model_name,
            # "gemini-3.5-flash",
            # "gemini-3.1-flash-lite",
            # "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]
        return list(dict.fromkeys(candidates))

    def _reset_daily_quota_state_if_needed(self) -> None:
        current_pt_date = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        if self._daily_exhausted_at != current_pt_date:
            self._daily_exhausted_models.clear()
            self._daily_exhausted_at = current_pt_date

    def _record_model_failure(self, model_name: str, error: Exception) -> None:
        error_text = str(error)
        if "429" not in error_text and "RESOURCE_EXHAUSTED" not in error_text:
            logger.warning(
                "Error with %s: %s; trying next model", model_name, error_text[:200]
            )
            return

        limit_type = self.parse_rate_limit_type(error_text)
        if limit_type == "daily":
            self._daily_exhausted_models.add(model_name)
            logger.warning(
                "%s daily quota exhausted; skipping for this session", model_name
            )
        elif limit_type == "minute":
            logger.warning("Rate limited on %s per minute; trying next model", model_name)
        else:
            logger.warning(
                "Rate limited on %s (type: %s); trying next model",
                model_name,
                limit_type,
            )

    @staticmethod
    def parse_rate_limit_type(error_text: str) -> str:
        """Return daily, minute, tokens, or unknown for a quota error."""
        error_lower = error_text.lower()
        if (
            "perday" in error_lower
            or "per_day" in error_lower
            or "requestsperday" in error_lower
            or "daily" in error_lower
        ):
            return "daily"
        if (
            "perminute" in error_lower
            or "per_minute" in error_lower
            or "requestsperminute" in error_lower
        ):
            return "minute"
        if "token" in error_lower:
            return "tokens"
        return "unknown"

    @staticmethod
    def _build_contents(
        messages: list[dict[str, str]], system: Optional[str]
    ) -> str:
        contents_parts = []
        if system:
            contents_parts.append(f"System: {system}")
        for message in messages:
            role = "User" if message["role"] == "user" else "Model"
            contents_parts.append(f"{role}: {message['content']}")
        return "\n\n".join(contents_parts)

    @staticmethod
    def _record_cost(
        task_type: Optional[str],
        model_name: str,
        contents: str,
        response_text: str,
    ) -> None:
        if not task_type:
            return
        input_tokens = estimate_tokens(contents)
        output_tokens = estimate_tokens(response_text)
        cost = ModelCascade.estimate_cost(task_type, input_tokens, output_tokens)
        get_cost_tracker().record(
            task_type=task_type,
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

