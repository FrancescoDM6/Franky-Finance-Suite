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
    from .synthesis import SynthesisService
    from .pdf_parser import PDFParserService
    from .structured_products import StructuredProductService
    from .cache_service import CacheService
    from .resource_monitor import ResourceMonitor
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

    @cached_property
    def synthesis(self) -> "SynthesisService":
        """Synthesis service (LLM-powered analysis generation)."""
        from .synthesis import SynthesisService

        return SynthesisService()

    def health_check(self) -> dict[str, bool]:
        """Check health of all services."""
        return {
            "db": self.db.health_check(),
            "llm": self.llm.health_check(),
            "market_data": self.market_data.health_check(),
        }

    @cached_property
    def pdf_parser(self) -> "PDFParserService":
        """PDF parsing service for structured notes."""
        from .pdf_parser import PDFParserService
        return PDFParserService()

    @cached_property
    def structured_products(self) -> "StructuredProductService":
        """Structured product valuation service."""
        from .structured_products import StructuredProductService
        return StructuredProductService()

    @cached_property
    def cache(self) -> "CacheService":
        """Cache service (DuckDB-backed with TTL)."""
        from .cache_service import get_cache_service
        return get_cache_service()

    @cached_property
    def resource_monitor(self) -> "ResourceMonitor":
        """Resource monitor for graceful degradation."""
        from .resource_monitor import get_resource_monitor
        return get_resource_monitor()


# Global service registry instance
services = ServiceRegistry()
