from datetime import datetime, timedelta

import pytest

from phinan.services.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
    with_timeout,
)


class TestCircuitBreakerStates:
    def test_new_breaker_is_closed(self):
        breaker = CircuitBreaker(name="test")
        state = breaker.get_state()

        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    def test_breaker_allows_request_when_closed(self):
        breaker = CircuitBreaker(name="test")

        assert breaker.allow_request() is True

    def test_breaker_opens_after_threshold_failures(self):
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        for _ in range(3):
            breaker.record_failure()

        state = breaker.get_state()
        assert state["state"] == "open"
        assert breaker.allow_request() is False

    def test_breaker_remains_closed_below_threshold(self):
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()

        state = breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 2

    def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()

        state = breaker.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0


class TestCircuitBreakerRecovery:
    def test_breaker_enters_half_open_after_timeout(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        breaker.record_failure()
        breaker.record_failure()

        assert breaker.get_state()["state"] == "open"

        breaker._last_failure_time = datetime.now() - timedelta(seconds=2)

        assert breaker.allow_request() is True
        assert breaker.get_state()["state"] == "half_open"

    def test_success_in_half_open_closes_breaker(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        breaker.record_failure()
        breaker.record_failure()
        breaker._last_failure_time = datetime.now() - timedelta(seconds=2)
        breaker.allow_request()

        breaker.record_success()

        assert breaker.get_state()["state"] == "closed"

    def test_failure_in_half_open_reopens_breaker(self):
        breaker = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)

        breaker.record_failure()
        breaker.record_failure()
        breaker._last_failure_time = datetime.now() - timedelta(seconds=2)
        breaker.allow_request()

        breaker.record_failure()

        assert breaker.get_state()["state"] == "open"

    def test_half_open_limits_concurrent_calls(self):
        breaker = CircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=1, half_open_max_calls=1
        )

        breaker.record_failure()
        breaker.record_failure()
        breaker._last_failure_time = datetime.now() - timedelta(seconds=2)

        first_result = breaker.allow_request()
        assert first_result is True
        assert breaker.get_state()["state"] == "half_open"

        second_result = breaker.allow_request()
        assert second_result is False


class TestCircuitBreakerRegistry:
    def test_get_circuit_breaker_creates_new(self):
        breaker = get_circuit_breaker("new-service")

        assert breaker.name == "new-service"
        assert breaker.get_state()["state"] == "closed"

    def test_get_circuit_breaker_returns_same_instance(self):
        breaker1 = get_circuit_breaker("same-service")
        breaker2 = get_circuit_breaker("same-service")

        assert breaker1 is breaker2

    def test_ollama_breaker_has_custom_config(self):
        breaker = get_circuit_breaker("ollama")

        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 60

    def test_gemini_breaker_has_custom_config(self):
        breaker = get_circuit_breaker("gemini")

        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 120


class TestWithTimeout:
    def test_returns_result_within_timeout(self):
        def fast_func():
            return "success"

        result = with_timeout(fast_func, 5)

        assert result == "success"

    def test_raises_timeout_error_when_exceeded(self):
        import time

        def slow_func():
            time.sleep(2)
            return "never returned"

        with pytest.raises(TimeoutError):
            with_timeout(slow_func, 0.1)

    def test_passes_arguments_to_function(self):
        def add_func(a, b):
            return a + b

        result = with_timeout(add_func, 5, 2, 3)

        assert result == 5
