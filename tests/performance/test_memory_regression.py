"""Memory regression tests to detect leaks and unbounded growth.

Run with: pytest tests/performance/test_memory_regression.py -v -m performance
"""

import gc
import time

import pytest

from phinan.core.memory import (
    get_memory_snapshot,
    track_memory,
    detect_memory_leak,
    force_gc_and_report,
    MemoryLeakDetector,
)


class TestMemoryUtilities:
    @pytest.mark.performance
    def test_memory_snapshot_returns_valid_data(self):
        snapshot = get_memory_snapshot()

        assert snapshot.current_mb >= 0
        assert snapshot.gc_objects > 0
        assert isinstance(snapshot.traced_mb, float)

    @pytest.mark.performance
    def test_track_memory_context_manager(self):
        with track_memory("test_block", threshold_mb=1000) as before:
            data = [i for i in range(10000)]
            _ = data

        assert before.gc_objects > 0

    @pytest.mark.performance
    def test_force_gc_returns_stats(self):
        _temp = [object() for _ in range(1000)]
        del _temp

        stats = force_gc_and_report()

        assert "before_objects" in stats
        assert "after_objects" in stats
        assert "collected_gen0" in stats

    @pytest.mark.performance
    def test_memory_leak_detector_baseline(self):
        detector = MemoryLeakDetector(
            check_interval_seconds=1.0, growth_threshold_mb=100.0
        )
        detector.set_baseline()

        result = detector.check()

        assert result is not None
        assert "current_mb" in result
        assert "growth_mb" in result
        assert result["growth_mb"] < 10


class TestMemoryStability:
    @pytest.mark.performance
    def test_repeated_dict_creation_no_leak(self):
        def create_dicts():
            data = {f"key_{i}": f"value_{i}" for i in range(1000)}
            return len(data)

        leak_detected, avg_growth = detect_memory_leak(
            create_dicts,
            iterations=20,
            threshold_mb_per_iter=0.5,
            warmup=3,
        )

        assert not leak_detected, f"Memory leak detected: {avg_growth:.2f} MB/iteration"

    @pytest.mark.performance
    def test_repeated_list_operations_no_leak(self):
        def list_operations():
            data = list(range(10000))
            filtered = [x for x in data if x % 2 == 0]
            sorted_data = sorted(filtered, reverse=True)
            return len(sorted_data)

        leak_detected, avg_growth = detect_memory_leak(
            list_operations,
            iterations=20,
            threshold_mb_per_iter=0.5,
            warmup=3,
        )

        assert not leak_detected, f"Memory leak detected: {avg_growth:.2f} MB/iteration"

    @pytest.mark.performance
    def test_cache_pattern_memory_bounded(self):
        cache_data = {}

        def mock_cache_get(key: str, data_type: str):
            return cache_data.get(f"{key}:{data_type}")

        def mock_cache_set(key: str, data_type: str, data):
            cache_data[f"{key}:{data_type}"] = data

        def cache_operations():
            for i in range(100):
                key = f"TICKER_{i}"
                result = mock_cache_get(key, "ticker_info")
                if result is None:
                    mock_cache_set(key, "ticker_info", {"symbol": key, "price": 100.0})
            cache_data.clear()

        leak_detected, avg_growth = detect_memory_leak(
            cache_operations,
            iterations=10,
            threshold_mb_per_iter=1.0,
            warmup=2,
        )

        assert not leak_detected, f"Cache pattern leak: {avg_growth:.2f} MB/iteration"


class TestPerformanceBaselines:
    BASELINES = {
        "dict_creation_10k": 0.01,
        "list_comprehension_100k": 0.02,
        "json_serialization_1k": 0.05,
    }

    @pytest.mark.performance
    def test_dict_creation_performance(self):
        def operation():
            return {f"key_{i}": i for i in range(10000)}

        elapsed = self._measure_operation(operation, iterations=100)
        avg_time = elapsed / 100

        baseline = self.BASELINES["dict_creation_10k"]
        assert avg_time < baseline * 2, (
            f"Dict creation regression: {avg_time:.4f}s (baseline: {baseline}s)"
        )

    @pytest.mark.performance
    def test_list_comprehension_performance(self):
        def operation():
            return [x * 2 for x in range(100000)]

        elapsed = self._measure_operation(operation, iterations=50)
        avg_time = elapsed / 50

        baseline = self.BASELINES["list_comprehension_100k"]
        assert avg_time < baseline * 2, (
            f"List comprehension regression: {avg_time:.4f}s (baseline: {baseline}s)"
        )

    @pytest.mark.performance
    def test_json_serialization_performance(self):
        import json

        data = {
            "ticker": "AAPL",
            "prices": [150.0 + i * 0.1 for i in range(1000)],
            "metadata": {"sector": "Technology", "exchange": "NASDAQ"},
        }

        def operation():
            serialized = json.dumps(data)
            return json.loads(serialized)

        elapsed = self._measure_operation(operation, iterations=1000)
        avg_time = elapsed / 1000

        baseline = self.BASELINES["json_serialization_1k"]
        assert avg_time < baseline * 2, (
            f"JSON serialization regression: {avg_time:.4f}s (baseline: {baseline}s)"
        )

    def _measure_operation(self, func, iterations: int) -> float:
        gc.collect()
        start = time.perf_counter()
        for _ in range(iterations):
            func()
        return time.perf_counter() - start


class TestAsyncMemoryStability:
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_run_sync_batch_memory_stable(self):
        from phinan.core.async_utils import run_sync_batch

        def simple_operation(n: int) -> int:
            return n * 2

        before = get_memory_snapshot()

        for _ in range(50):
            operations = [(simple_operation, i) for i in range(100)]
            results = await run_sync_batch(*operations)
            assert len(results) == 100

        gc.collect()
        after = get_memory_snapshot()

        growth = after.current_mb - before.current_mb
        assert growth < 20, f"Async batch memory growth: {growth:.2f} MB"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_operations_memory_bounded(self):
        import asyncio
        from phinan.core.async_utils import run_sync

        def allocate_and_release(size: int) -> int:
            data = [0] * size
            return len(data)

        before = get_memory_snapshot()

        for _ in range(20):
            tasks = [run_sync(allocate_and_release, 10000) for _ in range(10)]
            results = await asyncio.gather(*tasks)
            assert all(r == 10000 for r in results)

        gc.collect()
        after = get_memory_snapshot()

        growth = after.current_mb - before.current_mb
        assert growth < 30, f"Concurrent memory growth: {growth:.2f} MB"
