"""Market data service with OpenBB as primary and yfinance as fallback.

Design pattern: Data Provider Adapter
OpenBB provides a unified interface to multiple data sources.
yfinance kept as fallback for reliability.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Protocol
import logging

import pandas as pd

from ..config.settings import settings
from .cache_service import get_cache_service
from .circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)


@dataclass
class TickerInfo:
    """Standardized ticker information."""

    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    analyst_rating: Optional[str] = None
    target_price: Optional[float] = None
    num_analysts: Optional[int] = None
    current_price: Optional[float] = None


@dataclass
class PriceRange:
    """Price range analysis for a period."""

    period: str
    high: float
    low: float
    current: float
    percent_of_range: float


@dataclass
class NewsItem:
    """News article summary."""

    title: str
    publisher: str
    link: str
    published: datetime
    summary: Optional[str] = None


class DataProvider(Protocol):
    """Protocol for market data providers."""

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]: ...
    def get_price_history(
        self, symbol: str, period: str, interval: str
    ) -> pd.DataFrame: ...
    def get_news(self, symbol: str, max_items: int) -> list[NewsItem]: ...


class OpenBBProvider:
    """OpenBB 4.6.0-based data provider using the obb SDK.

    Fixed to work with OpenBB 4.6.0 actual API structure."""

    def __init__(self):
        self._obb = None
        self._provider = settings.market_data.openbb_provider
        self._breaker = get_circuit_breaker("openbb")

    def _get_obb(self):
        """Lazy-load OpenBB."""
        if self._obb is None:
            try:
                from openbb import obb

                self._obb = obb
            except ImportError:
                raise ImportError("openbb not installed. Run: pip install openbb[all]")
        return self._obb

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        """Get ticker info via OpenBB equity.profile and fundamental.metrics."""
        if not self._breaker.allow_request():
            return None

        try:
            obb = self._get_obb()

            # Use equity.profile for company info
            profile = obb.equity.profile(symbol, provider=self._provider)

            if (
                not hasattr(profile, "results")
                or profile.results is None
                or len(profile.results) == 0
            ):
                self._breaker.record_failure()
                return None

            data = profile.results[0]

            # Get current price from quote
            current_price = None
            try:
                quote = obb.equity.price.quote(symbol, provider=self._provider)
                if quote.results and len(quote.results) > 0:
                    # Use last_price which is correct attribute in OpenBB 4.6.0
                    current_price = getattr(quote.results[0], "last_price", None)
            except Exception as e:
                logger.error("OpenBB quote error for %s: %s", symbol, e)
                current_price = None

            # Fetch fundamental metrics (pe_ratio, profit_margin, etc.)
            # equity.profile doesn't include these, so we use fundamental.metrics
            pe_ratio = None
            dividend_yield = None
            profit_margin = None
            debt_to_equity = None

            try:
                metrics = obb.equity.fundamental.metrics(symbol, provider=self._provider)
                if hasattr(metrics, "results") and metrics.results:
                    m = metrics.results[0]
                    pe_ratio = getattr(m, "pe_ratio", None)
                    profit_margin = getattr(m, "profit_margin", None)
                    debt_to_equity = getattr(m, "debt_to_equity", None)
                    dividend_yield = getattr(m, "dividend_yield", None)

                    # Fix OpenBB dividend yield bug: returns percentage (e.g., 0.41)
                    # instead of decimal (e.g., 0.0041). Correct if value > 0.2 (20%)
                    if dividend_yield is not None and dividend_yield > 0.2:
                        dividend_yield = dividend_yield / 100

                    # Fix debt_to_equity scaling: yfinance returns as percentage
                    # (e.g., 152 meaning 1.52). Correct if value > 10
                    if debt_to_equity is not None and debt_to_equity > 10:
                        debt_to_equity = debt_to_equity / 100
            except Exception as e:
                logger.warning("Could not fetch fundamental metrics for %s: %s", symbol, e)

            # Fetch analyst estimates (rating, target price)
            analyst_rating = None
            target_price = None
            num_analysts = None

            try:
                consensus = obb.equity.estimates.consensus(symbol, provider=self._provider)
                if hasattr(consensus, "results") and consensus.results:
                    c = consensus.results[0]
                    analyst_rating = getattr(c, "recommendation", None)
                    target_price = getattr(c, "target_consensus", None) or getattr(
                        c, "target_median", None
                    )
                    num_analysts = getattr(c, "number_of_analysts", None)
            except Exception as e:
                logger.warning("Could not fetch analyst estimates for %s: %s", symbol, e)

            self._breaker.record_success()

            # Map OpenBB attributes to our TickerInfo structure
            return TickerInfo(
                symbol=symbol.upper(),
                name=getattr(data, "name", None)
                or getattr(data, "legal_name", None)
                or symbol,
                sector=getattr(data, "sector", None),
                industry=getattr(data, "industry_category", None)
                or getattr(data, "industry_group", None),
                market_cap=getattr(data, "market_cap", None),
                pe_ratio=pe_ratio,
                dividend_yield=dividend_yield,
                profit_margin=profit_margin,
                debt_to_equity=debt_to_equity,
                analyst_rating=analyst_rating,
                target_price=target_price,
                num_analysts=num_analysts,
                current_price=current_price,
            )

        except Exception as e:
            logger.error("OpenBB profile error for %s: %s", symbol, e)
            self._breaker.record_failure()
            return None


    def get_price_history(
        self, symbol: str, period: str = "6mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Get historical prices via OpenBB."""
        if not self._breaker.allow_request():
            return pd.DataFrame()

        try:
            obb = self._get_obb()

            # Convert period to start_date - OpenBB works better with start_date
            period_days = {
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
            }
            days = period_days.get(period, 180)
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            result = obb.equity.price.historical(
                symbol,
                start_date=start_date,
                provider=self._provider,
            )

            # Check if we have results and use to_df() method
            if hasattr(result, "results") and result.results:
                self._breaker.record_success()
                df = result.to_df()

                # Standardize column names to match expected format
                if df is not None and not df.empty:
                    df.columns = [c.title() for c in df.columns]
                    return df

            return pd.DataFrame()
        except Exception as e:
            logger.error(f"OpenBB price history error for {symbol}: {e}")
            self._breaker.record_failure()
            return pd.DataFrame()

    def get_news(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        """Get news via OpenBB."""
        if not self._breaker.allow_request():
            return []

        try:
            obb = self._get_obb()

            # Try to get news - note that news might require specific providers
            result = obb.news.company(symbol, limit=max_items, provider=self._provider)

            items = []
            if hasattr(result, "results") and result.results:
                self._breaker.record_success()
                for article in result.results[:max_items]:
                    # Handle date parsing robustly
                    published = getattr(article, "date", None) or datetime.now()
                    if isinstance(published, str):
                        try:
                            published = datetime.fromisoformat(
                                published.replace("Z", "+00:00")
                            )
                        except ValueError:
                            published = datetime.now()

                    # Map news attributes based on actual OpenBB news model
                    items.append(
                        NewsItem(
                            title=getattr(article, "title", ""),
                            publisher=getattr(article, "publisher", "")
                            or getattr(article, "source", ""),
                            link=getattr(article, "url", "")
                            or getattr(article, "link", ""),
                            published=published,
                            summary=getattr(article, "text", "")
                            or getattr(article, "summary", ""),
                        )
                    )
            return items
        except Exception as e:
            logger.error(f"OpenBB news error for {symbol}: {e}")
            self._breaker.record_failure()
            return []


class YFinanceProvider:
    """YFinance-based data provider (legacy/fallback)."""

    def __init__(self):
        self._yf = None

    def _get_yf(self):
        """Lazy-load yfinance."""
        if self._yf is None:
            try:
                import yfinance as yf

                self._yf = yf
            except ImportError:
                raise ImportError("yfinance not installed. Run: pip install yfinance")
        return self._yf

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        """Get ticker info via yfinance."""
        yf = self._get_yf()
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None:
                return None

            return TickerInfo(
                symbol=symbol.upper(),
                name=info.get("longName") or info.get("shortName") or symbol,
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                dividend_yield=info.get("dividendYield"),
                profit_margin=info.get("profitMargins"),
                debt_to_equity=info.get("debtToEquity"),
                analyst_rating=info.get("recommendationKey"),
                target_price=info.get("targetMeanPrice"),
                num_analysts=info.get("numberOfAnalystOpinions"),
                current_price=info.get("regularMarketPrice"),
            )
        except Exception as e:
            print(f"yfinance error for {symbol}: {e}")
            return None

    def get_price_history(
        self, symbol: str, period: str = "6mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Get historical prices via yfinance."""
        yf = self._get_yf()
        try:
            ticker = yf.Ticker(symbol)
            return ticker.history(period=period, interval=interval)
        except Exception as e:
            logger.error(f"yfinance price history error for {symbol}: {e}")
            return pd.DataFrame()

    def get_news(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        """Get news via yfinance."""
        yf = self._get_yf()
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news or []

            items = []
            for article in news[:max_items]:
                content = article.get("content", {})
                if not content:
                    continue

                provider = content.get("provider", {})
                pub_date_str = content.get("pubDate", "")

                try:
                    published = (
                        datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                        if pub_date_str
                        else datetime.now()
                    )
                except (ValueError, AttributeError):
                    published = datetime.now()

                items.append(
                    NewsItem(
                        title=content.get("title", ""),
                        publisher=provider.get("displayName", ""),
                        link=content.get("canonicalUrl", {}).get("url", ""),
                        published=published,
                        summary=content.get("summary", ""),
                    )
                )
            return items
        except Exception as e:
            logger.error(f"yfinance news error for {symbol}: {e}")
            return []


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

        # Initialize providers
        if self._provider_name == "openbb":
            self._primary = OpenBBProvider()
            self._fallback = YFinanceProvider()
        else:
            self._primary = YFinanceProvider()
            self._fallback = None

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
        from ..core.metrics import metrics, record_cache_hit, record_cache_miss

        cached = self._cache.get(symbol, "ticker_info")
        if cached:
            record_cache_hit("ticker_info")
            return TickerInfo(**cached)

        record_cache_miss("ticker_info")
        start = time.perf_counter()

        result = self._primary.get_ticker_info(symbol)

        if result is None and self._fallback:
            logger.warning(f"Primary provider failed for {symbol}, trying fallback...")
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
            print(
                f"Primary provider failed for price history {symbol}, trying fallback..."
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
        """Get available options expiration dates.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of expiration date strings
        """
        # Options always use yfinance fallback (more reliable)
        if self._fallback:
            yf = self._fallback._get_yf()
        else:
            # Create yfinance provider if needed
            try:
                import yfinance as yf_lib

                yf = yf_lib
            except ImportError:
                return []

        try:
            ticker = yf.Ticker(symbol)
            return list(ticker.options)
        except Exception:
            return []

    def get_options_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        """Get options chain data.

        Args:
            symbol: Stock ticker symbol
            expiration: Expiration date string (defaults to nearest)

        Returns:
            Dict with "calls" and "puts" DataFrames
        """
        # Options always use yfinance fallback (more reliable)
        if self._fallback:
            yf = self._fallback._get_yf()
        else:
            yf = self._primary._get_yf() if hasattr(self._primary, "_get_yf") else None
            if yf is None:
                return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

        try:
            ticker = yf.Ticker(symbol)

            if expiration is None:
                expirations = ticker.options
                if not expirations:
                    return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
                expiration = expirations[0]

            chain = ticker.option_chain(expiration)
            return {
                "calls": chain.calls,
                "puts": chain.puts,
            }
        except Exception as e:
            print(f"Error fetching options chain for {symbol}: {e}")
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

    def get_news(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        import time
        from ..core.metrics import metrics

        start = time.perf_counter()
        result = self._primary.get_news(symbol, max_items)

        if not result and self._fallback:
            logger.warning(
                f"Primary provider failed for news {symbol}, trying fallback..."
            )
            result = self._fallback.get_news(symbol, max_items)

        duration = time.perf_counter() - start
        metrics.market_data_duration.labels(
            operation="news", provider=self._provider_name
        ).observe(duration)

        return result

    def get_analyst_details(self, symbol: str) -> dict:
        """Get detailed analyst data including recommendation breakdown.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with recommendation_counts, price_targets, and recent_changes
        """
        # Analyst data always uses yfinance (most reliable)
        if self._fallback:
            yf = self._fallback._get_yf()
        else:
            yf = self._primary._get_yf() if hasattr(self._primary, "_get_yf") else None
            if yf is None:
                return self._empty_analyst_result()

        result = {
            "recommendation_counts": {
                "strong_buy": 0,
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "strong_sell": 0,
            },
            "price_targets": {
                "low": None,
                "mean": None,
                "median": None,
                "high": None,
            },
            "recent_changes": [],
        }

        try:
            ticker = yf.Ticker(symbol)

            # Get recommendations summary
            try:
                rec_summary = ticker.recommendations_summary
                if rec_summary is not None and not rec_summary.empty:
                    latest = rec_summary.iloc[0] if len(rec_summary) > 0 else None
                    if latest is not None:
                        result["recommendation_counts"] = {
                            "strong_buy": int(latest.get("strongBuy", 0)),
                            "buy": int(latest.get("buy", 0)),
                            "hold": int(latest.get("hold", 0)),
                            "sell": int(latest.get("sell", 0)),
                            "strong_sell": int(latest.get("strongSell", 0)),
                        }
            except Exception as e:
                print(f"Error fetching recommendations summary for {symbol}: {e}")

            # Get price targets
            try:
                info = ticker.info
                if info:
                    result["price_targets"] = {
                        "low": info.get("targetLowPrice"),
                        "mean": info.get("targetMeanPrice"),
                        "median": info.get("targetMedianPrice"),
                        "high": info.get("targetHighPrice"),
                    }
            except Exception as e:
                print(f"Error fetching price targets for {symbol}: {e}")

            # Get recent upgrades/downgrades
            try:
                upgrades = ticker.upgrades_downgrades
                if upgrades is not None and not upgrades.empty:
                    recent = upgrades.head(5)
                    for idx, row in recent.iterrows():
                        date_str = (
                            idx.strftime("%b %d")
                            if hasattr(idx, "strftime")
                            else str(idx)[:10]
                        )
                        result["recent_changes"].append(
                            {
                                "date": date_str,
                                "firm": row.get("Firm", "Unknown"),
                                "to_grade": row.get("ToGrade", ""),
                                "from_grade": row.get("FromGrade", ""),
                                "action": row.get("Action", ""),
                            }
                        )
            except Exception as e:
                print(f"Error fetching upgrades/downgrades for {symbol}: {e}")

            return result

        except Exception as e:
            print(f"Error fetching analyst details for {symbol}: {e}")
            return result

    def _empty_analyst_result(self) -> dict:
        """Return empty analyst result structure."""
        return {
            "recommendation_counts": {
                "strong_buy": 0,
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "strong_sell": 0,
            },
            "price_targets": {"low": None, "mean": None, "median": None, "high": None},
            "recent_changes": [],
        }

    async def get_ticker_info_async(self, symbol: str) -> Optional[TickerInfo]:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_ticker_info, symbol)

    async def get_price_range_async(
        self, symbol: str, period: str = "3mo"
    ) -> Optional[PriceRange]:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_price_range, symbol, period)

    async def get_news_async(self, symbol: str, max_items: int = 10) -> list[NewsItem]:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_news, symbol, max_items)

    async def get_analyst_details_async(self, symbol: str) -> dict:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_analyst_details, symbol)

    async def get_price_history_async(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_price_history, symbol, period, interval)

    async def get_options_expirations_async(self, symbol: str) -> list[str]:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_options_expirations, symbol)

    async def get_options_chain_async(
        self, symbol: str, expiration: Optional[str] = None
    ) -> dict[str, pd.DataFrame]:
        from ..core.async_utils import run_sync

        return await run_sync(self.get_options_chain, symbol, expiration)
