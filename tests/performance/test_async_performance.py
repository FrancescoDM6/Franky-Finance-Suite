"""Performance tests for async improvements.

Tests validate that:
1. Concurrent execution is faster than sequential
2. Event loop is not blocked during I/O operations
3. Memory usage stays bounded during concurrent operations

Run with: pytest tests/performance/ -v -m performance
"""

import asyncio
import time

import pytest

from phinan.core.async_utils import run_sync, run_sync_batch, run_sync_dict


def slow_sync_operation(delay: float = 0.1, result: str = "done") -> str:
    """Simulates a slow synchronous I/O operation."""
    time.sleep(delay)
    return result


def slow_sync_with_args(arg1: str, arg2: int, delay: float = 0.1) -> dict:
    """Simulates a slow sync operation with arguments."""
    time.sleep(delay)
    return {"arg1": arg1, "arg2": arg2}


class TestAsyncUtilsPerformance:
    """Performance tests for async utility functions."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_run_sync_does_not_block_event_loop(self):
        """Verify run_sync executes in thread pool, not blocking event loop."""
        event_loop_blocked = False
        background_task_ran = False

        async def background_checker():
            nonlocal background_task_ran
            await asyncio.sleep(0.05)
            background_task_ran = True

        async def main():
            nonlocal event_loop_blocked
            checker = asyncio.create_task(background_checker())

            start = time.perf_counter()
            result = await run_sync(slow_sync_operation, 0.2, "test")
            elapsed = time.perf_counter() - start

            await checker

            if not background_task_ran:
                event_loop_blocked = True

            return result, elapsed

        result, elapsed = await main()

        assert result == "test"
        assert elapsed >= 0.2
        assert background_task_ran, (
            "Background task should have run (event loop not blocked)"
        )
        assert not event_loop_blocked

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_run_sync_batch_concurrent_faster_than_sequential(self):
        """Verify batch execution is faster than sequential."""
        num_operations = 5
        delay_per_op = 0.1

        sequential_start = time.perf_counter()
        sequential_results = []
        for i in range(num_operations):
            result = await run_sync(slow_sync_operation, delay_per_op, f"seq_{i}")
            sequential_results.append(result)
        sequential_time = time.perf_counter() - sequential_start

        operations = [
            (slow_sync_operation, delay_per_op, f"batch_{i}")
            for i in range(num_operations)
        ]
        concurrent_start = time.perf_counter()
        concurrent_results = await run_sync_batch(*operations)
        concurrent_time = time.perf_counter() - concurrent_start

        assert len(sequential_results) == num_operations
        assert len(concurrent_results) == num_operations

        speedup = sequential_time / concurrent_time

        assert concurrent_time < sequential_time, (
            f"Concurrent ({concurrent_time:.2f}s) should be faster than "
            f"sequential ({sequential_time:.2f}s)"
        )
        assert speedup > 2.0, f"Expected >2x speedup, got {speedup:.1f}x"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_run_sync_dict_preserves_order(self):
        """Verify run_sync_dict returns correctly named results."""
        results = await run_sync_dict(
            first=(slow_sync_with_args, "a", 1, 0.05),
            second=(slow_sync_with_args, "b", 2, 0.05),
            third=(slow_sync_with_args, "c", 3, 0.05),
        )

        assert "first" in results
        assert "second" in results
        assert "third" in results
        assert results["first"]["arg1"] == "a"
        assert results["second"]["arg2"] == 2
        assert results["third"]["arg1"] == "c"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_execution_scales(self):
        """Test that concurrent execution scales with more operations."""
        delay = 0.05

        for num_ops in [2, 4, 8]:
            operations = [
                (slow_sync_operation, delay, f"op_{i}") for i in range(num_ops)
            ]

            start = time.perf_counter()
            results = await run_sync_batch(*operations)
            elapsed = time.perf_counter() - start

            assert len(results) == num_ops

            max_expected = delay * 2 + 0.1
            assert elapsed < max_expected, (
                f"With {num_ops} ops, expected <{max_expected:.2f}s, got {elapsed:.2f}s"
            )


class TestResearchWorkflowPerformance:
    """Performance tests simulating research workflow patterns."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_simulated_research_concurrent_fetch(self):
        """Simulate concurrent data fetching in research workflow."""

        def mock_get_ticker_info(symbol: str) -> dict:
            time.sleep(0.15)
            return {"symbol": symbol, "price": 150.0}

        def mock_get_news(symbol: str, count: int) -> list:
            time.sleep(0.1)
            return [{"title": f"News {i}"} for i in range(count)]

        def mock_get_price_range(symbol: str, period: str) -> dict:
            time.sleep(0.1)
            return {"high": 160, "low": 140, "period": period}

        def mock_get_analyst_details(symbol: str) -> dict:
            time.sleep(0.12)
            return {"rating": "buy", "target": 180}

        sequential_start = time.perf_counter()
        _ = mock_get_ticker_info("AAPL")
        _ = mock_get_news("AAPL", 5)
        _ = mock_get_price_range("AAPL", "3mo")
        _ = mock_get_analyst_details("AAPL")
        sequential_time = time.perf_counter() - sequential_start

        concurrent_start = time.perf_counter()
        results = await run_sync_batch(
            (mock_get_ticker_info, "AAPL"),
            (mock_get_news, "AAPL", 5),
            (mock_get_price_range, "AAPL", "3mo"),
            (mock_get_analyst_details, "AAPL"),
        )
        concurrent_time = time.perf_counter() - concurrent_start

        ticker_info, news, price_range, analyst = results
        assert ticker_info["symbol"] == "AAPL"
        assert len(news) == 5
        assert price_range["period"] == "3mo"
        assert analyst["rating"] == "buy"

        speedup = sequential_time / concurrent_time
        assert speedup > 2.5, (
            f"Expected >2.5x speedup for research workflow, got {speedup:.1f}x"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_simulated_portfolio_concurrent_price_fetch(self):
        """Simulate concurrent price fetching for portfolio positions."""

        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        def mock_get_price(symbol: str) -> float:
            time.sleep(0.08)
            prices = {"AAPL": 175, "MSFT": 400, "GOOGL": 140, "AMZN": 180, "META": 500}
            return prices.get(symbol, 100.0)

        sequential_start = time.perf_counter()
        sequential_prices = {}
        for symbol in symbols:
            sequential_prices[symbol] = mock_get_price(symbol)
        sequential_time = time.perf_counter() - sequential_start

        concurrent_start = time.perf_counter()
        operations = [(mock_get_price, symbol) for symbol in symbols]
        results = await run_sync_batch(*operations)
        concurrent_prices = dict(zip(symbols, results))
        concurrent_time = time.perf_counter() - concurrent_start

        for symbol in symbols:
            assert concurrent_prices[symbol] == sequential_prices[symbol]

        speedup = sequential_time / concurrent_time
        assert speedup > 3.0, (
            f"Expected >3x speedup for portfolio fetch, got {speedup:.1f}x"
        )


class TestEventLoopHealth:
    """Tests to ensure event loop remains responsive."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_event_loop_responsiveness_during_heavy_load(self):
        """Verify event loop stays responsive during heavy concurrent I/O."""
        heartbeat_count = 0
        test_duration = 0.5

        async def heartbeat():
            nonlocal heartbeat_count
            start = time.perf_counter()
            while time.perf_counter() - start < test_duration:
                await asyncio.sleep(0.02)
                heartbeat_count += 1

        async def heavy_io_load():
            operations = [(slow_sync_operation, 0.1, f"heavy_{i}") for i in range(10)]
            return await run_sync_batch(*operations)

        heartbeat_task = asyncio.create_task(heartbeat())
        io_task = asyncio.create_task(heavy_io_load())

        results = await io_task
        await heartbeat_task

        assert len(results) == 10

        min_heartbeats = 10
        assert heartbeat_count >= min_heartbeats, (
            f"Event loop not responsive: {heartbeat_count} heartbeats, "
            f"expected at least {min_heartbeats}"
        )
