"""Market data service facade with caching and provider fallback."""

import logging
from typing import Optional

import pandas as pd

from ...config.settings import settings
from ..cache_service import get_cache_service
from .models import (
    AnalystProvider,
    DataProvider,
    NewsItem,
    OptionsProvider,
    PriceRange,
    TickerInfo,
)
from .providers import OpenBBProvider, YFinanceProvider

logger = logging.getLogger(__name__)


class MarketDataService:
    """Market data service with provider abstraction.

    Uses OpenBB as primary provider with yfinance fallback.
    All data fetching goes through this service for:
    - Consistent error handling
    - Caching (via CacheService)
    - Circuit breaker protection
    """

    def __init__(self):
        """Initialize market data service."""
        self._cache = get_cache_service()
        self._provider_name = settings.market_data.provider

        yfinance = YFinanceProvider()
        self._primary: DataProvider
        self._fallback: Optional[DataProvider]
        if self._provider_name == "openbb":
            self._primary = OpenBBProvider()
            self._fallback = yfinance
        else:
            self._primary = yfinance
            self._fallback = None

        self._options_provider: OptionsProvider = yfinance
        self._analyst_provider: AnalystProvider = yfinance

    def health_check(self) -> bool:
        """Check if market data service is available."""
        import importlib.util
        try:
            if self._provider_name == "openbb":
                return importlib.util.find_spec("openbb") is not None
            return importlib.util.find_spec("yfinance") is not None
        except Exception:
            return False

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        import time
        from ...core.metrics import metrics, record_cache_hit, record_cache_miss

        cached = self._cache.get(symbol, "ticker_info")
        if cached:
            record_cache_hit("ticker_info")
            return TickerInfo(**cached)

        record_cache_miss("ticker_info")
        start = time.perf_counter()

        result = self._primary.get_ticker_info(symbol)

        if result is None and self._fallback:
            logger.warning("Primary provider failed for %s, trying fallback", symbol)
            result = self._fallback.get_ticker_info(symbol)

        duration = time.perf_counter() - start
        metrics.market_data_duration.labels(
            operation="ticker_info", provider=self._provider_name
        ).observe(duration)

        if result:
            self._cache.set(symbol, "ticker_info", result)

        return result

    def get_price_history(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Get historical price data.

        Args:
            symbol: Stock ticker symbol
            period: Time period (1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            interval: Data interval (1d, 1wk, 1mo)

        Returns:
            DataFrame with OHLCV data
        """
        # Try primary provider
        result = self._primary.get_price_history(symbol, period, interval)

        # Fallback if primary fails
        if result.empty and self._fallback:
            logger.warning(
                "Primary provider failed for price history %s, trying fallback",
                symbol,
            )
            result = self._fallback.get_price_history(symbol, period, interval)

        return result

    def get_price_range(self, symbol: str, period: str = "3mo") -> Optional[PriceRange]:
        """Calculate price range for period.

        Args:
            symbol: Stock ticker symbol
            period: Time period (1mo, 3mo, 6mo, 1y)

        Returns:
            PriceRange dataclass
        """
        # Check cache
        cached = self._cache.get(symbol, f"price_range_{period}")
        if cached:
            return PriceRange(**cached)

        history = self.get_price_history(symbol, period=period)

        if history.empty:
            return None

        high = history["High"].max()
        low = history["Low"].min()
        current = history["Close"].iloc[-1]

        # Calculate position in range (0 = at low, 1 = at high)
        range_size = high - low
        if range_size > 0:
            percent = (current - low) / range_size
        else:
            percent = 0.5

        result = PriceRange(
            period=period,
            high=float(high),
            low=float(low),
            current=float(current),
            percent_of_range=float(percent),
        )

        self._cache.set(symbol, f"price_range_{period}", result)
        return result

    def get_options_expirations(self, symbol: str) -> list[str]:
        """Get available options expiration dates."""
        return self._options_provider.get_options_expirations(symbol)

    def get_options_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        """Get an options chain from the configured options provider."""
        return self._options_provider.get_options_chain(symbol, expiration)

    def get_news(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        import time
        from ...core.metrics import metrics

        start = time.perf_counter()
        result = self._primary.get_news(symbol, max_items)

        if not result and self._fallback:
            logger.warning(
                "Primary provider failed for news %s, trying fallback", symbol
            )
            result = self._fallback.get_news(symbol, max_items)

        duration = time.perf_counter() - start
        metrics.market_data_duration.labels(
            operation="news", provider=self._provider_name
        ).observe(duration)

        return result

    def get_analyst_details(self, symbol: str) -> dict:
        """Get analyst details from the configured analyst provider."""
        return self._analyst_provider.get_analyst_details(symbol)

    async def get_ticker_info_async(self, symbol: str) -> Optional[TickerInfo]:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_ticker_info, symbol)

    async def get_price_range_async(
        self, symbol: str, period: str = "3mo"
    ) -> Optional[PriceRange]:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_price_range, symbol, period)

    async def get_news_async(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_news, symbol, max_items)

    async def get_analyst_details_async(self, symbol: str) -> dict:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_analyst_details, symbol)

    async def get_price_history_async(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_price_history, symbol, period, interval)

    async def get_options_expirations_async(self, symbol: str) -> list[str]:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_options_expirations, symbol)

    async def get_options_chain_async(
        self, symbol: str, expiration: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        from ...core.async_utils import run_sync

        return await run_sync(self.get_options_chain, symbol, expiration)

