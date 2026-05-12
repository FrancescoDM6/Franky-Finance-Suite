"""LLM service wrapping Google Gemini for cloud inference and Ollama for local fallback.

Design principles:
- Use LLM for: synthesis, explanation, exploration, multi-turn conversations
- Do NOT use LLM for: calculations, number extraction, classification

Pattern: "LLM extracts, Python calculates"
"""

from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo
import logging

from ..config.settings import settings
from .circuit_breaker import get_circuit_breaker, with_timeout, DEFAULT_LLM_TIMEOUT

logger = logging.getLogger(__name__)

APP_TIMEZONE = "America/New_York"
BASE_SYSTEM_MARKER = "PHINAN_RUNTIME_CONTEXT"


class LLMService:
    """LLM service supporting Gemini (cloud) with Ollama (local) fallback.

    Provides structured interfaces for:
    - Multi-turn chat conversations
    - Single-turn completions
    - Tool/function calling for assistant
    """

    def __init__(self):
        """Initialize LLM service."""
        self._gemini_client = None
        self._ollama_client = None
        self._use_gemini = bool(settings.gemini.api_key)
        self._gemini_model_name = settings.gemini.model
        self._ollama_model = settings.ollama.model
        self._ollama_base_url = settings.ollama.base_url
        # Track models that have exhausted daily quotas (resets at midnight PT)
        self._daily_exhausted_models: set[str] = set()
        self._daily_exhausted_at: Optional[date] = None

    def _get_gemini_client(self):
        """Lazy-load Gemini client (new SDK)."""
        if self._gemini_client is None:
            try:
                from google import genai

                self._gemini_client = genai.Client(api_key=settings.gemini.api_key)
            except ImportError:
                raise ImportError(
                    "google-genai package not installed. Run: pip install google-genai"
                )
        return self._gemini_client

    def _get_ollama_client(self):
        """Lazy-load Ollama client."""
        if self._ollama_client is None:
            try:
                import ollama

                self._ollama_client = ollama.Client(host=self._ollama_base_url)
            except ImportError:
                raise ImportError(
                    "Local AI fallback unavailable (ollama package not installed)."
                )
        return self._ollama_client

    def health_check(self) -> bool:
        """Check if LLM service is available (Gemini preferred, Ollama fallback)."""
        if self._use_gemini:
            try:
                # Quick check by creating client
                self._get_gemini_client()
                return True
            except Exception:
                pass

        # Fallback to Ollama
        try:
            client = self._get_ollama_client()
            client.list()
            return True
        except Exception:
            return False

    def _build_base_system_prompt(self) -> str:
        """Build shared runtime and finance policy for every LLM request."""
        now = datetime.now(ZoneInfo(APP_TIMEZONE))
        today = now.date().isoformat()
        timestamp = now.isoformat(timespec="seconds")

        return f"""[{BASE_SYSTEM_MARKER}]
Today is {today}.
Local timezone: {APP_TIMEZONE}.
Local timestamp: {timestamp}.

Use this injected date for all relative-date reasoning. Ignore any model training cutoff or stale built-in date awareness when deciding what today, tomorrow, yesterday, this week, or this month means.

Strict market-data policy:
- Do not claim current prices, market levels, rates, earnings, analyst changes, news, options availability, expiration dates, or corporate events unless they are present in the provided prompt/context.
- If fresh app data is missing or incomplete, say exactly what is missing and avoid filling gaps from model memory.
- When using provided market data, make clear which assumptions would invalidate the advice.

Finance advice style:
- Be direct, practical, profile-aware, and risk-aware.
- Separate observed app data from assumptions.
- Prefer an explicit action, no-action, or watchlist call when the prompt provides enough evidence.
- For options, only reference expiration dates, strikes, bids, IV, or open interest that appear in the context.
"""

    def _compose_system_prompt(self, system: Optional[str] = None) -> str:
        """Merge shared runtime policy with task-specific system instructions."""
        if system and BASE_SYSTEM_MARKER in system:
            return system

        base_system = self._build_base_system_prompt()
        if not system:
            return base_system

        return f"{base_system}\nTask-specific instructions:\n{system}"

    def chat(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        task_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Multi-turn chat completion with optional model cascading.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: Optional system prompt
            model: Model override (defaults to configured model)
            tools: Tool definitions for function calling
            task_type: Task type for model cascading (e.g., "sentiment_classification",
                       "research_synthesis"). If provided, uses ModelCascade to select
                       optimal model for cost efficiency.

        Returns:
            Response dict with "content" and optionally "tool_calls"
        """
        # Use model cascade if task_type provided and no explicit model override
        cascade_model = None
        if task_type and not model:
            from .model_cascade import ModelCascade
            cascade_model = ModelCascade.get_model_for_task(task_type).name

        if self._use_gemini:
            return self._chat_gemini(messages, system, tools, task_type, cascade_model)
        else:
            return self._chat_ollama(messages, system, model or cascade_model, tools)

    def _chat_gemini(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        task_type: Optional[str] = None,
        cascade_model: Optional[str] = None,
    ) -> dict[str, Any]:
        """Chat using Gemini API with smart fallback based on rate limit type."""
        from .model_cascade import get_cost_tracker, ModelCascade, estimate_tokens

        system = self._compose_system_prompt(system)

        # If cascade_model provided, use it first, otherwise use default chain
        if cascade_model:
            gemini_models = [cascade_model]
        else:
            # Fallback chain ordered by capability, then by free-tier daily quota:
            #   gemini-2.5-flash  (250 RPD)  - best quality flash
            #   gemini-2.0-flash  (1,500 RPD) - very capable, highest quota
            #   gemini-2.5-flash-lite (1,000 RPD) - lightweight 2.5
            #   gemini-2.0-flash-lite (1,500 RPD) - cheapest, highest quota
            # Total free-tier capacity: ~4,250 requests/day before Ollama fallback
            gemini_models = [
                self._gemini_model_name,
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.0-flash-lite",
            ]
        # Remove duplicates while preserving order
        seen = set()
        gemini_models = [m for m in gemini_models if not (m in seen or seen.add(m))]

        current_pt_date = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        if self._daily_exhausted_at != current_pt_date:
            self._daily_exhausted_models.clear()
            self._daily_exhausted_at = current_pt_date

        # Filter out daily-exhausted models
        available_models = [
            m for m in gemini_models if m not in self._daily_exhausted_models
        ]

        if not available_models:
            logger.warning(
                "All Gemini models daily quota exhausted, going directly to Ollama..."
            )
            try:
                return self._chat_ollama(messages, system, None, tools)
            except Exception as ollama_error:
                return {
                    "content": "AI analysis is temporarily unavailable — the daily API quota has been reached. Please try again tomorrow, or configure a local Ollama instance as a fallback.",
                    "error": True,
                }

        # Build contents string from messages
        contents_parts = []
        if system:
            contents_parts.append(f"System: {system}")

        for msg in messages:
            role = "User" if msg["role"] == "user" else "Model"
            contents_parts.append(f"{role}: {msg['content']}")

        contents = "\n\n".join(contents_parts)

        # Try each Gemini model in the fallback chain
        last_error = None
        for model_name in available_models:
            try:
                client = self._get_gemini_client()
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )

                # Track cost if task_type provided
                if task_type:
                    cost_tracker = get_cost_tracker()
                    input_tokens = estimate_tokens(contents)
                    output_tokens = estimate_tokens(response.text or "")
                    cost = ModelCascade.estimate_cost(task_type, input_tokens, output_tokens)
                    cost_tracker.record(
                        task_type=task_type,
                        model=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost,
                    )

                result = {
                    "content": response.text,
                    "model": model_name,
                }
                logger.info("LLM response from %s (%d chars)", model_name, len(response.text or ""))
                return result

            except Exception as e:
                error_str = str(e)
                last_error = e

                # Check if it's a rate limit error
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    limit_type = self._parse_rate_limit_type(error_str)

                    if limit_type == "daily":
                        # Model is exhausted for the day - don't try again
                        self._daily_exhausted_models.add(model_name)
                        logger.warning(
                            "%s DAILY quota exhausted (resets at midnight PT). Skipping for this session.",
                            model_name,
                        )
                    elif limit_type == "minute":
                        # Could retry after a minute, but we'll just move to next model
                        logger.warning(
                            "Rate limited on %s (per-minute), trying next model...",
                            model_name,
                        )
                    else:
                        logger.warning(
                            "Rate limited on %s (type: %s), trying next model...",
                            model_name,
                            limit_type,
                        )
                    continue
                else:
                    # For non-rate-limit errors, still try next model
                    logger.warning("Error with %s: %s, trying next...", model_name, error_str[:200])
                    continue

        # All Gemini models failed, fallback to Ollama
        logger.warning(
            "All %d Gemini models exhausted (tried: %s), falling back to Ollama...",
            len(available_models),
            ", ".join(available_models),
        )
        
        # Try Ollama as a last resort
        ollama_result = None
        try:
            ollama_result = self._chat_ollama(messages, system, None, tools)
        except Exception as e:
            logger.warning("Ollama fallback failed with exception: %s", e)
            
        # If Ollama succeeded (no error flag), return its response
        if ollama_result and not ollama_result.get("error"):
            return ollama_result
            
        # If Ollama failed (or timed out), we want to show the user why the primary API failed
        if ollama_result:
            logger.warning("Ollama fallback failed: %s", ollama_result.get("content"))
            
        # Determine user-friendly message based on the original Gemini error
        last_err_str = str(last_error) if last_error else ""
        if "429" in last_err_str or "RESOURCE_EXHAUSTED" in last_err_str:
            user_msg = "AI analysis is temporarily unavailable — the API rate limit has been reached. Please wait a few minutes and try again."
        else:
            user_msg = "AI analysis is temporarily unavailable. Please check your API configuration and try again."
            
        return {
            "content": user_msg,
            "error": True,
        }

    def _parse_rate_limit_type(self, error_str: str) -> str:
        """Parse the type of rate limit from error message.

        Returns: 'daily', 'minute', 'tokens', or 'unknown'
        """
        error_lower = error_str.lower()

        # Check for daily limit indicators
        if (
            "perday" in error_lower
            or "per_day" in error_lower
            or "requestsperday" in error_lower
        ):
            return "daily"
        if "daily" in error_lower:
            return "daily"

        # Check for minute limit indicators
        if (
            "perminute" in error_lower
            or "per_minute" in error_lower
            or "requestsperminute" in error_lower
        ):
            return "minute"

        # Check for token limits
        if "token" in error_lower:
            return "tokens"

        return "unknown"

    def _chat_ollama(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """Chat using Ollama (local) API with circuit breaker and timeout."""
        breaker = get_circuit_breaker("ollama")
        system = self._compose_system_prompt(system)

        # Check circuit breaker
        if not breaker.allow_request():
            return {
                "content": "Local LLM temporarily unavailable (circuit open). Please try again later.",
                "error": True,
                "circuit_open": True,
            }

        client = self._get_ollama_client()
        model = model or self._ollama_model

        # Build messages with optional system prompt
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        def _do_chat():
            return client.chat(
                model=model,
                messages=full_messages,
                tools=tools,
            )

        try:
            # Execute with timeout protection
            response = with_timeout(_do_chat, DEFAULT_LLM_TIMEOUT)
            breaker.record_success()

            result = {
                "content": response["message"]["content"],
                "model": model,
            }

            # Include tool calls if present
            if "tool_calls" in response["message"]:
                result["tool_calls"] = response["message"]["tool_calls"]

            return result

        except TimeoutError as e:
            breaker.record_failure()
            return {
                "content": f"Ollama request timed out after {DEFAULT_LLM_TIMEOUT}s. Try a shorter prompt or check if Ollama is overloaded.",
                "error": True,
                "timeout": True,
            }
        except Exception as e:
            breaker.record_failure()
            return {
                "content": f"Error communicating with Ollama: {str(e)}",
                "error": True,
            }

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """Single-turn completion with optional model cascading.

        Args:
            prompt: The prompt to complete
            system: Optional system prompt
            model: Model override
            task_type: Task type for model cascading (optional)

        Returns:
            Completion text
        """
        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            model=model,
            task_type=task_type,
        )
        
        # If the cascade returned an error (quota, timeout, etc), raise it
        # so calling services don't cache/display the error message as valid analysis
        if response.get("error"):
            raise RuntimeError(response.get("content", "LLM completion failed"))
            
        return response.get("content", "")

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Stream chat response token by token.

        Yields:
            Token strings as they're generated
        """
        if self._use_gemini:
            yield from self._stream_gemini(messages, system)
        else:
            yield from self._stream_ollama(messages, system, model)

    def _stream_gemini(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
    ):
        """Stream using Gemini API (new google-genai SDK)."""
        try:
            client = self._get_gemini_client()
            system = self._compose_system_prompt(system)

            # Build contents string from messages
            contents_parts = []
            if system:
                contents_parts.append(f"System: {system}")

            for msg in messages:
                role = "User" if msg["role"] == "user" else "Model"
                contents_parts.append(f"{role}: {msg['content']}")

            contents = "\n\n".join(contents_parts)

            # Use the new SDK streaming syntax
            for chunk in client.models.generate_content_stream(
                model=self._gemini_model_name,
                contents=contents,
            ):
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            yield f"Error: {str(e)}"

    def _stream_ollama(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Stream using Ollama API."""
        client = self._get_ollama_client()
        model = model or self._ollama_model
        system = self._compose_system_prompt(system)

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        try:
            response = client.chat(
                model=model,
                messages=full_messages,
                stream=True,
            )

            for chunk in response:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except Exception as e:
            yield f"Error: {str(e)}"

    async def chat_async(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        from ..core.async_utils import run_sync

        return await run_sync(self.chat, messages, system, model, tools)

    async def complete_async(
        self, prompt: str, system: Optional[str] = None, model: Optional[str] = None
    ) -> str:
        from ..core.async_utils import run_sync

        return await run_sync(self.complete, prompt, system, model)
