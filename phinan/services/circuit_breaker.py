"""Circuit breaker and timeout utilities for agent resilience.

Provides protection against:
- Slow/hung LLM calls (timeouts)
- Cascading failures (circuit breaker pattern)
- Infinite tool loops (max iterations)
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Usage:
        breaker = CircuitBreaker(name="ollama", failure_threshold=3)

        if breaker.allow_request():
            try:
                result = call_ollama()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            # Circuit is open, fail fast
            return fallback_response()
    """

    name: str
    failure_threshold: int = 3  # Failures before opening
    recovery_timeout: int = 30  # Seconds before trying again
    half_open_max_calls: int = 1  # Calls allowed in half-open state

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = datetime.now() - self._last_failure_time
                    if elapsed > timedelta(seconds=self.recovery_timeout):
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 1
                        logger.info("Circuit '%s' entering HALF_OPEN state", self.name)
                        return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

        return False

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("Circuit '%s' recovered, closing", self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test
                self._state = CircuitState.OPEN
                logger.warning("Circuit '%s' failed recovery, reopening", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' OPEN after %s failures",
                    self.name,
                    self._failure_count,
                )

    def get_state(self) -> dict:
        """Get current circuit state."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
        }


def with_timeout(func: Callable, timeout_seconds: float, *args, **kwargs) -> Any:
    """Execute a function with a timeout.

    Args:
        func: Function to execute
        timeout_seconds: Maximum seconds to wait
        *args, **kwargs: Arguments to pass to function

    Returns:
        Function result

    Raises:
        TimeoutError: If function doesn't complete in time
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout_seconds}s")


@dataclass
class AgentGuard:
    """Guard for agent execution with limits.

    Prevents infinite loops and excessive resource usage during agent turns.

    Usage:
        guard = AgentGuard(max_tool_calls=5, max_duration_seconds=30)

        while guard.can_continue():
            tool_result = execute_tool(...)
            guard.record_tool_call()
    """

    max_tool_calls: int = 5
    max_duration_seconds: float = 30.0

    _tool_call_count: int = field(default=0, init=False)
    _start_time: Optional[float] = field(default=None, init=False)

    def start(self):
        """Start a new agent turn."""
        self._tool_call_count = 0
        self._start_time = time.time()

    def can_continue(self) -> tuple[bool, str]:
        """Check if agent can continue executing.

        Returns:
            (can_continue, reason) tuple
        """
        if self._start_time is None:
            self.start()

        # Check tool call limit
        if self._tool_call_count >= self.max_tool_calls:
            return False, f"Reached max tool calls ({self.max_tool_calls})"

        # Check duration limit
        elapsed = time.time() - self._start_time
        if elapsed >= self.max_duration_seconds:
            return False, f"Reached time limit ({self.max_duration_seconds}s)"

        return True, "ok"

    def record_tool_call(self):
        """Record that a tool was called."""
        self._tool_call_count += 1

    def get_stats(self) -> dict:
        """Get current execution stats."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "tool_calls": self._tool_call_count,
            "max_tool_calls": self.max_tool_calls,
            "elapsed_seconds": round(elapsed, 2),
            "max_duration": self.max_duration_seconds,
        }


# Default circuit breakers for common services
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breaker_lock = threading.Lock()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a service (thread-safe)."""
    # Double-checked locking pattern
    if name not in _circuit_breakers:
        with _breaker_lock:
            if name not in _circuit_breakers:
                # Configure based on service type
                if name == "ollama":
                    _circuit_breakers[name] = CircuitBreaker(
                        name=name,
                        failure_threshold=3,
                        recovery_timeout=60,  # Ollama might need time to recover
                    )
                elif name == "gemini":
                    _circuit_breakers[name] = CircuitBreaker(
                        name=name,
                        failure_threshold=5,
                        recovery_timeout=120,  # Rate limits might need longer
                    )
                else:
                    _circuit_breakers[name] = CircuitBreaker(name=name)
    return _circuit_breakers[name]


# Default timeouts (can be overridden via env vars)
DEFAULT_LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))
DEFAULT_TOOL_TIMEOUT = float(os.environ.get("TOOL_TIMEOUT_SECONDS", "15"))
