"""Market data service with OpenBB as primary and yfinance as fallback.

Design pattern: Data Provider Adapter
OpenBB provides a unified interface to multiple data sources.
yfinance kept as fallback for reliability.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Protocol

import pandas as pd

from ..config.settings import settings
from .cache_service import get_cache_service
from .circuit_breaker import get_circuit_breaker


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
        """Get ticker info via OpenBB equity.profile."""
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
                print(f"OpenBB quote error for {symbol}: {e}")
                current_price = None

            self._breaker.record_success()

            # Map OpenBB attributes to our TickerInfo structure
            # Based on actual testing of YFinanceEquityProfileData model
            return TickerInfo(
                symbol=symbol.upper(),
                name=getattr(data, "name", None)
                or getattr(data, "legal_name", None)
                or symbol,
                sector=getattr(data, "sector", None),
                industry=getattr(data, "industry_category", None)
                or getattr(data, "industry_group", None),
                market_cap=getattr(data, "market_cap", None),
                pe_ratio=getattr(data, "pe_ratio", None),
                dividend_yield=getattr(data, "dividend_yield", None),
                profit_margin=getattr(data, "profit_margin", None),
                debt_to_equity=getattr(data, "debt_to_equity", None),
                analyst_rating=None,  # Requires separate call
                target_price=None,
                num_analysts=None,
                current_price=current_price,
            )
        except Exception as e:
            print(f"OpenBB profile error for {symbol}: {e}")
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
            print(f"OpenBB price history error for {symbol}: {e}")
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
            print(f"OpenBB news error for {symbol}: {e}")
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
            print(f"yfinance price history error for {symbol}: {e}")
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
        try:
            if self._provider_name == "openbb":
                from openbb import obb
            else:
                import yfinance
            return True
        except Exception:
            return False

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        """Get comprehensive ticker information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            TickerInfo dataclass or None if not found
        """
        # Check cache first
        cached = self._cache.get(symbol, "ticker_info")
        if cached:
            return TickerInfo(**cached)

        # Try primary provider
        result = self._primary.get_ticker_info(symbol)

        # Fallback if primary fails
        if result is None and self._fallback:
            print(f"Primary provider failed for {symbol}, trying fallback...")
            result = self._fallback.get_ticker_info(symbol)

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
        """Get recent news for a ticker.

        Args:
            symbol: Stock ticker symbol
            max_items: Maximum news items to return

        Returns:
            List of NewsItem dataclasses
        """
        # Try primary provider
        result = self._primary.get_news(symbol, max_items)

        # Fallback if primary fails
        if not result and self._fallback:
            print(f"Primary provider failed for news {symbol}, trying fallback...")
            result = self._fallback.get_news(symbol, max_items)

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
