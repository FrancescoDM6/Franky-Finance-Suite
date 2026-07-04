"""Public LLM service facade and prompt policy."""

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ...config.settings import settings
from .gemini import GeminiBackend
from .ollama import OllamaBackend

APP_TIMEZONE = "America/New_York"
BASE_SYSTEM_MARKER = "PHINAN_RUNTIME_CONTEXT"


class LLMService:
    """Route LLM requests between Gemini and Ollama backends."""

    def __init__(self):
        self._use_gemini = bool(settings.gemini.api_key)
        self._gemini = GeminiBackend(
            api_key=settings.gemini.api_key,
            model_name=settings.gemini.model,
        )
        self._ollama = OllamaBackend(
            base_url=settings.ollama.base_url,
            model=settings.ollama.model,
        )

    def health_check(self) -> bool:
        """Check Gemini first, then the Ollama fallback."""
        if self._use_gemini and self._gemini.health_check():
            return True
        return self._ollama.health_check()

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
        """Merge shared runtime policy with task-specific instructions."""
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
        """Run a multi-turn chat completion with configured fallback behavior."""
        cascade_model = None
        if task_type and not model:
            cascade_model = self._gemini.model_for_task(task_type)

        composed_system = self._compose_system_prompt(system)
        if self._use_gemini:
            return self._gemini.chat(
                messages=messages,
                system=composed_system,
                tools=tools,
                task_type=task_type,
                cascade_model=cascade_model,
                ollama_fallback=self._ollama.chat,
            )
        return self._ollama.chat(
            messages,
            composed_system,
            model or cascade_model,
            tools,
        )

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """Run a single-turn completion."""
        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            model=model,
            task_type=task_type,
        )
        if response.get("error"):
            raise RuntimeError(response.get("content", "LLM completion failed"))
        return response.get("content", "")

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Stream a response from the configured backend."""
        composed_system = self._compose_system_prompt(system)
        if self._use_gemini:
            yield from self._gemini.stream(messages, composed_system)
        else:
            yield from self._ollama.stream(messages, composed_system, model)

    async def chat_async(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        from ...core.async_utils import run_sync

        return await run_sync(self.chat, messages, system, model, tools)

    async def complete_async(
        self, prompt: str, system: Optional[str] = None, model: Optional[str] = None
    ) -> str:
        from ...core.async_utils import run_sync

        return await run_sync(self.complete, prompt, system, model)

