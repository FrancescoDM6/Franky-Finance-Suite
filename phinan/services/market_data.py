"""Market data service abstracting yfinance (swappable to Polygon).

Design pattern: Data Provider Adapter
yfinance breaks often - interface is stable, implementation swappable.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from ..config.settings import settings
from ..core.database import get_database_manager
import json
from dataclasses import asdict
from datetime import timedelta


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


class MarketDataService:
    """Market data service using yfinance.

    All data fetching goes through this service for:
    - Consistent error handling
    - Caching (via database cache table)
    - Easy swap to different provider
    """

    def __init__(self):
        """Initialize market data service."""
        self._provider = settings.market_data.provider
        self._cache_ttl = settings.market_data.cache_ttl_minutes
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

    def health_check(self) -> bool:
        """Check if market data service is available."""
        try:
            self._get_yf()
            return True
        except Exception:
            return False

    def _get_cached_data(self, symbol: str, data_type: str) -> Optional[dict]:
        """Get data from cache if valid."""
        try:
            db_mgr = get_database_manager()
            # CURRENT_TIMESTAMP in SQL is usually UTC. datetime.now() is local?
            # It's safer to rely on DB for time comparison if possible, or ensure consistency.
            # Using simple comparison for now.
            query = """
                SELECT data FROM market_data_cache 
                WHERE ticker_symbol = ? AND data_type = ? AND expires_at > CURRENT_TIMESTAMP
            """
            result = db_mgr.query(query, (symbol.upper(), data_type))
            if result:
                # DuckDB returns dict if we use our wrapper properly
                # But result[0]['data'] might be a string (JSON)
                # Check if it needs loading
                data_val = result[0]['data']
                if isinstance(data_val, str):
                    return json.loads(data_val)
                return data_val # If driver auto-converts JSON type
        except Exception as e:
            # Silent fail on cache error to fallback to live data
            print(f"Cache read error for {symbol}: {e}")
        return None

    def _set_cached_data(self, symbol: str, data_type: str, data: Any):
        """Save data to cache."""
        try:
            db_mgr = get_database_manager()
            expires_at = datetime.now() + timedelta(minutes=self._cache_ttl)
            
            # Serialize data if it's a dataclass, otherwise assume dict
            if hasattr(data, '__dataclass_fields__'):
                data_dict = asdict(data)
            else:
                data_dict = data
                
            query = """
                INSERT INTO market_data_cache 
                (id, ticker_symbol, data_type, data, expires_at, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker_symbol, data_type) DO UPDATE SET
                    data = excluded.data,
                    expires_at = excluded.expires_at,
                    cached_at = excluded.cached_at
            """
            
            import random
            # Generate random 32-bit integer for ID since DuckDB INTEGER is 32-bit
            cache_id = random.randint(0, 2**31 - 1)
            now = datetime.now()
            db_mgr.execute(query, (cache_id, symbol.upper(), data_type, json.dumps(data_dict), expires_at, now))
        except Exception as e:
            print(f"Cache write error for {symbol}: {e}")

    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        """Get comprehensive ticker information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            TickerInfo dataclass or None if not found
        """
        yf = self._get_yf()

        # Check cache first
        cached = self._get_cached_data(symbol, "ticker_info")
        if cached:
            return TickerInfo(**cached)

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Handle case where ticker doesn't exist
            if not info or info.get("regularMarketPrice") is None:
                return None

            result = TickerInfo(
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
            
            # Cache the result
            self._set_cached_data(symbol, "ticker_info", result)
            return result
        except Exception as e:
            print(f"Error fetching ticker info for {symbol}: {e}")
            return None

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
        yf = self._get_yf()

        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period=period, interval=interval)
            return history
        except Exception as e:
            print(f"Error fetching price history for {symbol}: {e}")
            return pd.DataFrame()

    def get_price_range(self, symbol: str, period: str = "3mo") -> Optional[PriceRange]:
        """Calculate price range for period.

        Args:
            symbol: Stock ticker symbol
            period: Time period (1mo, 3mo, 6mo, 1y)

        Returns:
            PriceRange dataclass
        """
        # Check cache
        cached = self._get_cached_data(symbol, f"price_range_{period}")
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
        
        self._set_cached_data(symbol, f"price_range_{period}", result)
        return result

    def get_options_expirations(self, symbol: str) -> list[str]:
        """Get available options expiration dates.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of expiration date strings
        """
        yf = self._get_yf()

        try:
            ticker = yf.Ticker(symbol)
            return list(ticker.options)
        except Exception:
            return []

    def get_options_chain(self, symbol: str, expiration: Optional[str] = None) -> dict[str, pd.DataFrame]:
        """Get options chain data.

        Args:
            symbol: Stock ticker symbol
            expiration: Expiration date string (defaults to nearest)

        Returns:
            Dict with "calls" and "puts" DataFrames
        """
        yf = self._get_yf()

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
        yf = self._get_yf()

        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news or []

            items = []
            for article in news[:max_items]:
                items.append(
                    NewsItem(
                        title=article.get("title", ""),
                        publisher=article.get("publisher", ""),
                        link=article.get("link", ""),
                        published=datetime.fromtimestamp(article.get("providerPublishTime", 0)),
                        summary=article.get("summary"),
                    )
                )
            return items
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return []
