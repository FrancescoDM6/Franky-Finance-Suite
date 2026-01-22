"""Performance monitoring utilities for tracking operation timing.

Provides lightweight timing utilities and optional Prometheus metrics
integration for production monitoring.

Usage:
    from phinan.core.performance import timed, get_metrics

    @timed("research_workflow")
    async def research_ticker():
        ...

    with timed("market_data_fetch"):
        data = services.market_data.get_ticker_info("AAPL")
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_metrics_enabled = False
_prometheus_available = False
_histograms: dict[str, Any] = {}

try:
    from prometheus_client import Histogram, Counter, Gauge

    _prometheus_available = True
except ImportError:
    pass


def enable_metrics():
    global _metrics_enabled
    if _prometheus_available:
        _metrics_enabled = True
        logger.info("Prometheus metrics enabled")
    else:
        logger.warning("prometheus_client not installed, metrics disabled")


def _get_histogram(name: str) -> Optional[Any]:
    if not _metrics_enabled or not _prometheus_available:
        return None

    if name not in _histograms:
        from prometheus_client import Histogram

        _histograms[name] = Histogram(
            f"phinan_{name}_duration_seconds",
            f"Duration of {name} operations",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )
    return _histograms[name]


@contextmanager
def timed(operation_name: str, log_threshold_ms: float = 1000.0):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000

        if elapsed_ms >= log_threshold_ms:
            logger.info("%s completed in %.1fms", operation_name, elapsed_ms)

        histogram = _get_histogram(operation_name)
        if histogram:
            histogram.observe(elapsed_ms / 1000)


def timed_async(operation_name: str, log_threshold_ms: float = 1000.0):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if elapsed_ms >= log_threshold_ms:
                    logger.info("%s completed in %.1fms", operation_name, elapsed_ms)
                histogram = _get_histogram(operation_name)
                if histogram:
                    histogram.observe(elapsed_ms / 1000)

        return wrapper

    return decorator


def get_metrics() -> dict[str, float]:
    if not _metrics_enabled:
        return {}

    result = {}
    for name, histogram in _histograms.items():
        try:
            samples = list(histogram.collect())[0].samples
            for sample in samples:
                if sample.name.endswith("_count"):
                    result[f"{name}_count"] = sample.value
                elif sample.name.endswith("_sum"):
                    result[f"{name}_sum_seconds"] = sample.value
        except Exception:
            pass
    return result
