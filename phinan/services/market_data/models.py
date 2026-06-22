"""Market data domain models and provider interface."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

import pandas as pd


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


class OptionsProvider(Protocol):
    """Protocol for options-market data providers."""

    def get_options_expirations(self, symbol: str) -> list[str]: ...

    def get_options_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> dict[str, pd.DataFrame]: ...


class AnalystProvider(Protocol):
    """Protocol for analyst-research data providers."""

    def get_analyst_details(self, symbol: str) -> dict[str, Any]: ...
