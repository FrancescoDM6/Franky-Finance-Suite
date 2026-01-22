"""Memory leak detection and monitoring utilities.

Provides tools for tracking memory usage, detecting leaks, and profiling
memory consumption during development and production.
"""

import gc
import logging
import sys
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    current_mb: float
    peak_mb: float
    traced_mb: float
    gc_objects: int


@dataclass
class MemoryDelta:
    before: MemorySnapshot
    after: MemorySnapshot
    delta_mb: float
    delta_objects: int
    top_allocations: list[tuple[str, float]]


def get_memory_snapshot() -> MemorySnapshot:
    """Capture current memory state."""
    gc.collect()

    try:
        import psutil

        process = psutil.Process()
        current_mb = process.memory_info().rss / 1024 / 1024
        peak_mb = current_mb
    except ImportError:
        current_mb = 0.0
        peak_mb = 0.0

    traced_mb = 0.0
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        traced_mb = current / 1024 / 1024

    return MemorySnapshot(
        current_mb=round(current_mb, 2),
        peak_mb=round(peak_mb, 2),
        traced_mb=round(traced_mb, 2),
        gc_objects=len(gc.get_objects()),
    )


def start_memory_tracing(frames: int = 10):
    """Start tracemalloc for detailed allocation tracking."""
    if not tracemalloc.is_tracing():
        tracemalloc.start(frames)
        logger.info("Memory tracing started with %d frames", frames)


def stop_memory_tracing() -> Optional[list[tuple[str, float]]]:
    """Stop tracemalloc and return top allocations."""
    if not tracemalloc.is_tracing():
        return None

    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snapshot.statistics("lineno")[:20]
    return [(str(stat.traceback), stat.size / 1024 / 1024) for stat in top_stats]


@contextmanager
def track_memory(label: str = "operation", threshold_mb: float = 10.0):
    """Context manager to track memory usage of a code block.

    Logs warning if memory grows more than threshold.

    Usage:
        with track_memory("research_workflow", threshold_mb=50):
            await execute_research()
    """
    gc.collect()
    before = get_memory_snapshot()

    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start(5)

    try:
        yield before
    finally:
        gc.collect()
        after = get_memory_snapshot()
        delta = after.current_mb - before.current_mb

        if delta > threshold_mb:
            logger.warning(
                "Memory growth in '%s': %.2f MB (threshold: %.2f MB)",
                label,
                delta,
                threshold_mb,
            )

            if tracemalloc.is_tracing():
                snapshot = tracemalloc.take_snapshot()
                top = snapshot.statistics("lineno")[:5]
                for stat in top:
                    logger.warning(
                        "  Top alloc: %s - %.2f KB", stat.traceback, stat.size / 1024
                    )

        if not was_tracing:
            tracemalloc.stop()


def detect_memory_leak(
    func: Callable,
    iterations: int = 10,
    threshold_mb_per_iter: float = 1.0,
    warmup: int = 2,
) -> tuple[bool, float]:
    """Run function multiple times to detect memory leaks.

    Returns (leak_detected, avg_growth_per_iteration_mb).
    """
    gc.collect()

    for _ in range(warmup):
        func()
    gc.collect()

    start_snapshot = get_memory_snapshot()

    for _ in range(iterations):
        func()
    gc.collect()

    end_snapshot = get_memory_snapshot()

    total_growth = end_snapshot.current_mb - start_snapshot.current_mb
    avg_growth = total_growth / iterations

    leak_detected = avg_growth > threshold_mb_per_iter

    if leak_detected:
        logger.warning(
            "Potential memory leak detected: %.2f MB/iteration (threshold: %.2f)",
            avg_growth,
            threshold_mb_per_iter,
        )

    return leak_detected, avg_growth


def get_large_objects(min_size_kb: float = 100) -> list[tuple[type, int, float]]:
    """Find large objects in memory for leak investigation."""
    gc.collect()

    large_objects = []
    for obj in gc.get_objects():
        try:
            size = sys.getsizeof(obj)
            size_kb = size / 1024
            if size_kb >= min_size_kb:
                large_objects.append((type(obj), id(obj), size_kb))
        except (TypeError, ReferenceError):
            continue

    large_objects.sort(key=lambda x: x[2], reverse=True)
    return large_objects[:50]


def force_gc_and_report() -> dict:
    """Force garbage collection and report stats."""
    before_count = len(gc.get_objects())

    collected = [gc.collect(gen) for gen in range(3)]

    after_count = len(gc.get_objects())

    return {
        "before_objects": before_count,
        "after_objects": after_count,
        "freed_objects": before_count - after_count,
        "collected_gen0": collected[0],
        "collected_gen1": collected[1],
        "collected_gen2": collected[2],
    }


class MemoryLeakDetector:
    """Long-running memory leak detector for production monitoring."""

    def __init__(
        self, check_interval_seconds: float = 60.0, growth_threshold_mb: float = 50.0
    ):
        self._check_interval = check_interval_seconds
        self._threshold = growth_threshold_mb
        self._baseline: Optional[MemorySnapshot] = None
        self._history: list[MemorySnapshot] = []
        self._max_history = 100

    def set_baseline(self):
        gc.collect()
        self._baseline = get_memory_snapshot()
        self._history = [self._baseline]
        logger.info("Memory baseline set: %.2f MB", self._baseline.current_mb)

    def check(self) -> Optional[dict]:
        """Check for memory growth since baseline."""
        if self._baseline is None:
            self.set_baseline()
            return None

        current = get_memory_snapshot()
        self._history.append(current)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        growth = current.current_mb - self._baseline.current_mb

        result = {
            "current_mb": current.current_mb,
            "baseline_mb": self._baseline.current_mb,
            "growth_mb": growth,
            "gc_objects": current.gc_objects,
            "leak_suspected": growth > self._threshold,
        }

        if result["leak_suspected"]:
            logger.warning(
                "Memory leak suspected: %.2f MB growth (threshold: %.2f MB)",
                growth,
                self._threshold,
            )

        return result

    def get_trend(self) -> Optional[float]:
        """Calculate MB/hour growth trend from history."""
        if len(self._history) < 3:
            return None

        first = self._history[0]
        last = self._history[-1]

        samples = len(self._history)
        total_growth = last.current_mb - first.current_mb

        growth_per_sample = total_growth / samples if samples > 1 else 0
        samples_per_hour = 3600 / self._check_interval

        return growth_per_sample * samples_per_hour


_detector: Optional[MemoryLeakDetector] = None


def get_leak_detector(
    check_interval: float = 60.0, threshold_mb: float = 50.0
) -> MemoryLeakDetector:
    """Get singleton memory leak detector."""
    global _detector
    if _detector is None:
        _detector = MemoryLeakDetector(check_interval, threshold_mb)
    return _detector
