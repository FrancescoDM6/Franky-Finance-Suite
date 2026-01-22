"""Prometheus metrics for Phinan Finance Suite.

Centralized metric definitions for monitoring application performance.
Metrics are created lazily on first access to avoid import-time errors
if prometheus_client is not installed.

Usage:
    from phinan.core.metrics import metrics

    # Record research workflow duration
    with metrics.research_duration.labels(ticker="AAPL").time():
        await execute_research()

    # Increment counter
    metrics.cache_hits.labels(data_type="ticker_info").inc()

    # Set gauge
    metrics.active_research_sessions.set(5)
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_prometheus_available = False
_initialized = False

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        REGISTRY,
        generate_latest,
    )

    _prometheus_available = True
except ImportError:
    pass


class MetricsRegistry:
    def __init__(self):
        self._metrics: dict[str, Any] = {}
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized or not _prometheus_available:
            return
        self._create_metrics()
        self._initialized = True

    def _create_metrics(self):
        from prometheus_client import Counter, Histogram, Gauge, Info

        self._metrics["research_duration"] = Histogram(
            "phinan_research_duration_seconds",
            "Time to complete research workflow",
            ["ticker"],
            buckets=(1, 2, 5, 10, 20, 30, 60, 120),
        )

        self._metrics["market_data_duration"] = Histogram(
            "phinan_market_data_duration_seconds",
            "Time to fetch market data",
            ["operation", "provider"],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
        )

        self._metrics["llm_duration"] = Histogram(
            "phinan_llm_duration_seconds",
            "Time for LLM operations",
            ["operation", "model"],
            buckets=(1, 2, 5, 10, 30, 60, 120),
        )

        self._metrics["cache_hits"] = Counter(
            "phinan_cache_hits_total", "Total cache hits", ["data_type"]
        )

        self._metrics["cache_misses"] = Counter(
            "phinan_cache_misses_total", "Total cache misses", ["data_type"]
        )

        self._metrics["api_requests"] = Counter(
            "phinan_api_requests_total",
            "Total API requests",
            ["endpoint", "method", "status"],
        )

        self._metrics["active_research_sessions"] = Gauge(
            "phinan_active_research_sessions", "Number of active research sessions"
        )

        self._metrics["portfolio_positions"] = Gauge(
            "phinan_portfolio_positions_total", "Total portfolio positions"
        )

        self._metrics["portfolio_value"] = Gauge(
            "phinan_portfolio_value_dollars", "Total portfolio value in dollars"
        )

        self._metrics["errors"] = Counter(
            "phinan_errors_total", "Total errors", ["service", "error_type"]
        )

        self._metrics["sentiment_analysis_duration"] = Histogram(
            "phinan_sentiment_analysis_duration_seconds",
            "Time for sentiment analysis",
            ["batch_size"],
            buckets=(0.1, 0.5, 1, 2, 5, 10),
        )

        self._metrics["db_query_duration"] = Histogram(
            "phinan_db_query_duration_seconds",
            "Database query duration",
            ["operation"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1, 5),
        )

        self._metrics["app_info"] = Info("phinan_app", "Application information")
        self._metrics["app_info"].info({"version": "1.0.0", "framework": "reflex"})

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        self._ensure_initialized()

        if name in self._metrics:
            return self._metrics[name]

        if not _prometheus_available:
            return _NoOpMetric()

        raise AttributeError(f"Metric '{name}' not defined")

    @property
    def available(self) -> bool:
        return _prometheus_available

    def generate_latest(self) -> bytes:
        if not _prometheus_available:
            return b"# Prometheus client not installed\n"
        self._ensure_initialized()
        from prometheus_client import generate_latest, REGISTRY

        return generate_latest(REGISTRY)


class _NoOpMetric:
    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def set(self, value):
        pass

    def observe(self, value):
        pass

    def info(self, val):
        pass

    @contextmanager
    def time(self):
        yield


metrics = MetricsRegistry()


@contextmanager
def timed_operation(metric_name: str, **labels):
    if not _prometheus_available:
        yield
        return

    metrics._ensure_initialized()
    metric = metrics._metrics.get(metric_name)
    if metric is None:
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if labels:
            metric.labels(**labels).observe(duration)
        else:
            metric.observe(duration)


def record_error(service: str, error_type: str):
    if _prometheus_available:
        metrics.errors.labels(service=service, error_type=error_type).inc()


def record_cache_hit(data_type: str):
    if _prometheus_available:
        metrics.cache_hits.labels(data_type=data_type).inc()


def record_cache_miss(data_type: str):
    if _prometheus_available:
        metrics.cache_misses.labels(data_type=data_type).inc()
