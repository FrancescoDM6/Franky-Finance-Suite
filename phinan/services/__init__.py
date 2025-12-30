"""Service registry with lazy loading.

All expensive services (AI models, database connections) are loaded on first access.
This prevents slow startup times from loading models that aren't immediately needed.

Usage:
    from phinan.services import services

    # Services loaded only when accessed
    services.llm.chat(...)
    services.market_data.get_ticker_info("AAPL")
    services.db.query("SELECT * FROM portfolio")
"""

from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLMService
    from .market_data import MarketDataService
    from .sentiment import SentimentService
    from .volatility import VolatilityService
    from .embeddings import EmbeddingService
    from ..core.database import DatabaseManager


class ServiceRegistry:
    """Lazy-loaded service registry.

    Services are initialized on first access via cached_property.
    Thread-safe for singleton services.
    """

    @cached_property
    def db(self) -> "DatabaseManager":
        """Database service."""
        from ..core.database import get_database_manager

        return get_database_manager()

    @cached_property
    def llm(self) -> "LLMService":
        """LLM service (Ollama)."""
        from .llm import LLMService

        return LLMService()

    @cached_property
    def market_data(self) -> "MarketDataService":
        """Market data service (yfinance)."""
        from .market_data import MarketDataService

        return MarketDataService()

    @cached_property
    def sentiment(self) -> "SentimentService":
        """Sentiment analysis service (FinBERT)."""
        from .sentiment import SentimentService

        return SentimentService()

    @cached_property
    def volatility(self) -> "VolatilityService":
        """Volatility forecasting service (GARCH)."""
        from .volatility import VolatilityService

        return VolatilityService()

    @cached_property
    def embeddings(self) -> "EmbeddingService":
        """Embedding service (sentence-transformers)."""
        from .embeddings import EmbeddingService

        return EmbeddingService()

    def health_check(self) -> dict[str, bool]:
        """Check health of all services."""
        return {
            "db": self.db.health_check(),
            "llm": self.llm.health_check(),
            "market_data": self.market_data.health_check(),
        }


# Global service registry instance
services = ServiceRegistry()
