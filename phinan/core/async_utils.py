"""Async utilities for non-blocking execution of synchronous operations.

This module provides utilities to prevent event loop blocking when calling
synchronous I/O operations (database queries, network requests, etc.) from
async contexts like Reflex state handlers.

Usage:
    from phinan.core.async_utils import run_sync, run_sync_batch

    # Single operation
    result = await run_sync(services.market_data.get_ticker_info, "AAPL")

    # Multiple operations in parallel
    results = await run_sync_batch(
        (services.market_data.get_ticker_info, "AAPL"),
        (services.market_data.get_news, "AAPL", 10),
        (services.market_data.get_price_range, "AAPL", "3mo"),
    )
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# Shared thread pool for I/O-bound sync operations
# Size matches typical concurrent operations in research workflow
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="phinan_async_")

T = TypeVar("T")


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous function in a thread pool without blocking the event loop.

    This is the primary way to call sync I/O operations (database, network)
    from async Reflex state handlers.

    Args:
        func: Synchronous function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call

    Example:
        info = await run_sync(services.market_data.get_ticker_info, "AAPL")
    """
    loop = asyncio.get_running_loop()

    if kwargs:
        func = partial(func, **kwargs)

    return await loop.run_in_executor(_executor, func, *args)


async def run_sync_batch(*operations: tuple) -> list[Any]:
    """Run multiple synchronous operations concurrently.

    Each operation is a tuple of (func, *args). All operations run in parallel
    using TaskGroup for structured concurrency with fail-fast behavior.

    Args:
        *operations: Tuples of (callable, *args) to execute

    Returns:
        List of results in same order as operations

    Example:
        ticker_info, news, price_range = await run_sync_batch(
            (services.market_data.get_ticker_info, "AAPL"),
            (services.market_data.get_news, "AAPL", 10),
            (services.market_data.get_price_range, "AAPL", "3mo"),
        )
    """
    tasks = []
    results = [None] * len(operations)

    async def _run_and_store(idx: int, func, *args):
        results[idx] = await run_sync(func, *args)

    try:
        async with asyncio.TaskGroup() as tg:
            for i, op in enumerate(operations):
                if not op:
                    continue
                func = op[0]
                args = op[1:] if len(op) > 1 else ()
                tg.create_task(_run_and_store(i, func, *args))
    except* Exception:
        pass  # Return partial results on error

    return results


async def run_sync_dict(**named_operations: tuple) -> dict[str, Any]:
    """Run multiple synchronous operations concurrently with named results.

    Like run_sync_batch but returns a dictionary with named results,
    making code more readable when dealing with many operations.

    Args:
        **named_operations: Named tuples of (callable, *args) to execute

    Returns:
        Dict mapping names to results

    Example:
        results = await run_sync_dict(
            ticker_info=(services.market_data.get_ticker_info, "AAPL"),
            news=(services.market_data.get_news, "AAPL", 10),
            price_range=(services.market_data.get_price_range, "AAPL", "3mo"),
        )
        info = results["ticker_info"]
        news = results["news"]
    """
    names = list(named_operations.keys())
    operations = list(named_operations.values())

    results = await run_sync_batch(*operations)

    return dict(zip(names, results))


def shutdown_executor():
    """Shutdown the thread pool executor gracefully.

    Called automatically on application exit via atexit, but can be
    called manually if needed.
    """
    _executor.shutdown(wait=False)


import atexit

atexit.register(shutdown_executor)
