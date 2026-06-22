"""YFinance market data, options, and analyst provider adapter."""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from ..models import NewsItem, TickerInfo

logger = logging.getLogger(__name__)


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
            logger.error("yfinance error for %s: %s", symbol, e)
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
            logger.error("yfinance price history error for %s: %s", symbol, e)
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
            logger.error("yfinance news error for %s: %s", symbol, e)
            return []

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
        except Exception as e:
            logger.error("Error fetching options expirations for %s: %s", symbol, e)
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
            logger.error("Error fetching options chain for %s: %s", symbol, e)
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

    def get_analyst_details(self, symbol: str) -> dict:
        """Get detailed analyst data including recommendation breakdown.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dict with recommendation_counts, price_targets, and recent_changes
        """
        yf = self._get_yf()

        result = self._empty_analyst_result()

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
                logger.warning(
                    "Error fetching recommendations summary for %s: %s", symbol, e
                )

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
                logger.warning("Error fetching price targets for %s: %s", symbol, e)

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
                logger.warning(
                    "Error fetching upgrades/downgrades for %s: %s", symbol, e
                )

            return result

        except Exception as e:
            logger.error("Error fetching analyst details for %s: %s", symbol, e)
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
