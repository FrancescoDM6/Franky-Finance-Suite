"""Local Ollama backend for the LLM service."""

from typing import Any, Optional

from ..circuit_breaker import DEFAULT_LLM_TIMEOUT, get_circuit_breaker, with_timeout


class OllamaBackend:
    """Ollama client with circuit-breaker, timeout, and streaming support."""

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url
        self._model = model
        self._client = None

    def _get_client(self):
        """Lazy-load the Ollama client."""
        if self._client is None:
            try:
                import ollama

                self._client = ollama.Client(host=self._base_url)
            except ImportError:
                raise ImportError(
                    "Local AI fallback unavailable (ollama package not installed)."
                )
        return self._client

    def health_check(self) -> bool:
        """Check whether the Ollama server responds."""
        try:
            self._get_client().list()
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
        """Chat using Ollama with circuit-breaker and timeout protection."""
        breaker = get_circuit_breaker("ollama")
        if not breaker.allow_request():
            return {
                "content": (
                    "Local LLM temporarily unavailable (circuit open). "
                    "Please try again later."
                ),
                "error": True,
                "circuit_open": True,
            }

        client = self._get_client()
        selected_model = model or self._model
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        def do_chat():
            return client.chat(
                model=selected_model,
                messages=full_messages,
                tools=tools,
            )

        try:
            response = with_timeout(do_chat, DEFAULT_LLM_TIMEOUT)
            breaker.record_success()
            result = {
                "content": response["message"]["content"],
                "model": selected_model,
            }
            if "tool_calls" in response["message"]:
                result["tool_calls"] = response["message"]["tool_calls"]
            return result
        except TimeoutError:
            breaker.record_failure()
            return {
                "content": (
                    f"Ollama request timed out after {DEFAULT_LLM_TIMEOUT}s. "
                    "Try a shorter prompt or check if Ollama is overloaded."
                ),
                "error": True,
                "timeout": True,
            }
        except Exception as e:
            breaker.record_failure()
            return {
                "content": f"Error communicating with Ollama: {str(e)}",
                "error": True,
            }

    def stream(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Stream an Ollama response token by token.

        Each chunk read is guarded by an inactivity timeout so a stalled
        stream cannot hang the caller indefinitely. Failures and timeouts
        feed the shared Ollama circuit breaker, same as chat().
        """
        from concurrent.futures import (
            ThreadPoolExecutor,
            TimeoutError as FuturesTimeoutError,
        )

        breaker = get_circuit_breaker("ollama")
        if not breaker.allow_request():
            yield (
                "Local LLM temporarily unavailable (circuit open). "
                "Please try again later."
            )
            return

        client = self._get_client()
        selected_model = model or self._model
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        sentinel = object()
        # One reused worker thread for the whole stream; shut down with
        # wait=False so a hung next() cannot block the generator's exit.
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            response = client.chat(
                model=selected_model,
                messages=full_messages,
                stream=True,
            )
            iterator = iter(response)
            while True:
                future = executor.submit(next, iterator, sentinel)
                try:
                    chunk = future.result(timeout=DEFAULT_LLM_TIMEOUT)
                except FuturesTimeoutError:
                    breaker.record_failure()
                    yield (
                        f"\n[Ollama stream stalled: no data for "
                        f"{DEFAULT_LLM_TIMEOUT:.0f}s]"
                    )
                    return
                if chunk is sentinel:
                    break
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            yield f"Error: {str(e)}"
        finally:
            executor.shutdown(wait=False)

