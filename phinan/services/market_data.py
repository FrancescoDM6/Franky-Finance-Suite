"""Market data service abstracting yfinance (swappable to Polygon).

Design pattern: Data Provider Adapter
yfinance breaks often - interface is stable, implementation swappable.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from ..config.settings import settings
from .cache_service import get_cache_service


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
        self._cache = get_cache_service()
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



    def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
        """Get comprehensive ticker information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            TickerInfo dataclass or None if not found
        """
        yf = self._get_yf()

        # Check cache first
        cached = self._cache.get(symbol, "ticker_info")
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
            self._cache.set(symbol, "ticker_info", result)
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
                # yfinance API changed: news data is now under article['content']
                content = article.get("content", {})
                if not content:
                    continue
                    
                provider = content.get("provider", {})
                pub_date_str = content.get("pubDate", "")
                
                # Parse ISO format date
                try:
                    published = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")) if pub_date_str else datetime.now()
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
            print(f"Error fetching news for {symbol}: {e}")
            return []

    def get_analyst_details(self, symbol: str) -> dict:
        """Get detailed analyst data including recommendation breakdown.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with recommendation_counts, price_targets, and recent_changes
        """
        yf = self._get_yf()

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
                    # Get the most recent row (index 0 is usually 0m = current month)
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
                    # Get the 5 most recent changes
                    recent = upgrades.head(5)
                    for idx, row in recent.iterrows():
                        # idx is the date, row contains firm, toGrade, fromGrade, action
                        date_str = idx.strftime("%b %d") if hasattr(idx, 'strftime') else str(idx)[:10]
                        result["recent_changes"].append({
                            "date": date_str,
                            "firm": row.get("Firm", "Unknown"),
                            "to_grade": row.get("ToGrade", ""),
                            "from_grade": row.get("FromGrade", ""),
                            "action": row.get("Action", ""),
                        })
            except Exception as e:
                print(f"Error fetching upgrades/downgrades for {symbol}: {e}")

            return result

        except Exception as e:
            print(f"Error fetching analyst details for {symbol}: {e}")
            return result
