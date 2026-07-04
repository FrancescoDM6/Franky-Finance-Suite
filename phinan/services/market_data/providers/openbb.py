"""OpenBB market data provider adapter."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from ....config.settings import settings
from ...circuit_breaker import get_circuit_breaker
from ..models import NewsItem, TickerInfo

logger = logging.getLogger(__name__)


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
            logger.error("OpenBB price history error for %s: %s", symbol, e)
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
            logger.error("OpenBB news error for %s: %s", symbol, e)
            self._breaker.record_failure()
            return []

