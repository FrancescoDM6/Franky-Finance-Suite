"""LLM service wrapping Ollama for local inference.

Design principles:
- Use LLM for: synthesis, explanation, exploration, multi-turn conversations
- Do NOT use LLM for: calculations, number extraction, classification

Pattern: "LLM extracts, Python calculates"
"""

from typing import Any, Optional

from ..config.settings import settings


class LLMService:
    """Ollama LLM service for chat and completions.

    Provides structured interfaces for:
    - Multi-turn chat conversations
    - Single-turn completions
    - Tool/function calling for assistant
    """

    def __init__(self):
        """Initialize LLM service."""
        self._client = None
        self._model = settings.ollama.model
        self._base_url = settings.ollama.base_url
        self._timeout = settings.ollama.timeout

    def _get_client(self):
        """Lazy-load Ollama client."""
        if self._client is None:
            try:
                import ollama

                self._client = ollama.Client(host=self._base_url)
            except ImportError:
                raise ImportError("ollama package not installed. Run: pip install ollama")
        return self._client

    def health_check(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            client = self._get_client()
            # List models to verify connection
            client.list()
            return True
        except Exception:
            return False

    def chat(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """Multi-turn chat completion.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: Optional system prompt
            model: Model override (defaults to configured model)
            tools: Tool definitions for function calling

        Returns:
            Response dict with "content" and optionally "tool_calls"
        """
        client = self._get_client()
        model = model or self._model

        # Build messages with optional system prompt
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        try:
            response = client.chat(
                model=model,
                messages=full_messages,
                tools=tools,
            )

            result = {
                "content": response["message"]["content"],
                "model": model,
            }

            # Include tool calls if present
            if "tool_calls" in response["message"]:
                result["tool_calls"] = response["message"]["tool_calls"]

            return result

        except Exception as e:
            return {
                "content": f"Error communicating with LLM: {str(e)}",
                "error": True,
            }

    def complete(self, prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
        """Single-turn completion.

        Args:
            prompt: The prompt to complete
            system: Optional system prompt
            model: Model override

        Returns:
            Completion text
        """
        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            model=model,
        )
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
        client = self._get_client()
        model = model or self._model

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
