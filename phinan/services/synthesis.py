"""Synthesis service for generating LLM-powered analysis.

Provides reusable synthesis generation for research analysis,
bank recommendation evaluation, and theme research.
"""

from dataclasses import dataclass
from typing import Any, Optional
import hashlib

from ..modules.research.prompts import (
    build_analysis_prompt,
    build_bank_rec_prompt,
    build_theme_prompt,
)


from datetime import datetime, timedelta
import json
# from ..core.database import get_database_manager - moved inside methods to prevent circular import

@dataclass
class ResearchContext:
    """Context data for generating research synthesis."""

    ticker: str
    ticker_info: dict[str, Any]
    price_range: dict[str, Any]
    analyst_data: dict[str, Any]
    quality_check: dict[str, Any]
    news_sentiment: str
    profile_name: str
    profile_description: str
    timeframe: str
    default_range: str
    portfolio_position: Optional[dict[str, Any]] = None
    options_summary: str = ""
    options_expiration: str = ""


@dataclass
class SynthesisResult:
    """Result from synthesis generation."""

    content: str
    success: bool
    error: Optional[str] = None
    cached: bool = False


class SynthesisService:
    """Service for generating LLM synthesis of research data.

    Abstracts the synthesis logic from state management, making it
    reusable across different modules and contexts.
    """

    # Cache TTL: 1 hour max (user positions and market data change frequently)
    CACHE_TTL_HOURS = 1

    def __init__(self):
        """Initialize synthesis service."""
        self._llm = None
        # Cache validity period (1 hour - positions/prices change)
        self._cache_validity = timedelta(hours=self.CACHE_TTL_HOURS)

    def _compute_context_hash(self, context: ResearchContext) -> str:
        """Generate hash of context to detect staleness.

        Cache invalidates when any of these change:
        - Current price (rounded to avoid noise)
        - Portfolio position (quantity, cost basis, P/L)
        - News sentiment
        - User profile
        - Options expiration
        """
        # Extract key fields that should invalidate cache
        hash_data = {
            "ticker": context.ticker,
            "profile": context.profile_name,
            "sentiment": context.news_sentiment,
            "options_exp": context.options_expiration,
            # Round price to nearest dollar to avoid noise from minor fluctuations
            "price": round(context.ticker_info.get("current_price", 0) or 0),
            # Include position info if present
            "position": None,
        }

        if context.portfolio_position:
            hash_data["position"] = {
                "qty": context.portfolio_position.get("quantity"),
                "cost": round(context.portfolio_position.get("cost_basis", 0) or 0),
            }

        # Create stable hash
        hash_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_str.encode()).hexdigest()[:12]

    def _get_llm(self):
        """Lazy-load LLM service."""
        if self._llm is None:
            from . import services

            self._llm = services.llm
        return self._llm

    def _get_cached_synthesis(self, ticker: str, research_type: str, context_hash: str) -> Optional[str]:
        """Get valid cached synthesis from database.

        Args:
            ticker: Stock ticker symbol
            research_type: Type of research (e.g., 'synthesis_full')
            context_hash: Hash of context to ensure cache is still valid

        Returns:
            Cached synthesis content if valid, None otherwise
        """
        try:
            from ..core.database import get_database_manager
            db_mgr = get_database_manager()
            # Check for recent synthesis with matching context hash
            query = """
                SELECT data FROM research
                WHERE ticker_symbol = ? AND research_type = ?
                AND created_at > ?
                ORDER BY created_at DESC LIMIT 1
            """
            cutoff_time = datetime.now() - self._cache_validity
            result = db_mgr.query(query, (ticker.upper(), research_type, cutoff_time))

            if result:
                data = result[0]['data']
                if isinstance(data, str):
                    data = json.loads(data)

                # Check context hash matches (cache invalidation on context change)
                cached_hash = data.get("context_hash")
                if cached_hash != context_hash:
                    # Context changed - cache is stale
                    return None

                return data.get("content")
            return None
        except Exception as e:
            print(f"Cache read error: {e}")
            return None

    def _cache_synthesis(self, ticker: str, research_type: str, content: str, context_hash: str):
        """Save synthesis to database cache.

        Args:
            ticker: Stock ticker symbol
            research_type: Type of research
            content: Generated synthesis content
            context_hash: Hash of context for staleness detection
        """
        try:
            from ..core.database import get_database_manager
            db_mgr = get_database_manager()

            # Store content with context hash for staleness detection
            data = {"content": content, "context_hash": context_hash}

            query = """
                INSERT INTO research (ticker_symbol, research_type, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """
            now = datetime.now()
            db_mgr.execute(query, (ticker.upper(), research_type, json.dumps(data), now, now))
        except Exception as e:
            print(f"Cache write error: {e}")

    def health_check(self) -> bool:
        """Check if synthesis service is available (requires LLM)."""
        try:
            return self._get_llm().health_check()
        except Exception:
            return False

    def generate_research_synthesis(
        self, context: ResearchContext, force_refresh: bool = False
    ) -> SynthesisResult:
        """Generate research synthesis for a ticker.

        Args:
            context: ResearchContext with all research data
            force_refresh: If True, bypass cache and regenerate

        Returns:
            SynthesisResult with generated content or error
        """
        if not self.health_check():
            return SynthesisResult(
                content="",
                success=False,
                error="LLM service unavailable",
            )

        # Compute context hash for cache key
        context_hash = self._compute_context_hash(context)

        # Check cache first (unless force refresh requested)
        if not force_refresh:
            cached_result = self._get_cached_synthesis(
                context.ticker, "synthesis_full", context_hash
            )
            if cached_result:
                return SynthesisResult(
                    content=cached_result,
                    success=True,
                    cached=True
                )

        try:
            prompt = build_analysis_prompt(
                ticker=context.ticker,
                ticker_info=context.ticker_info,
                price_range=context.price_range,
                analyst_data=context.analyst_data,
                quality_check=context.quality_check,
                news_sentiment=context.news_sentiment,
                profile_name=context.profile_name,
                profile_description=context.profile_description,
                timeframe=context.timeframe,
                default_range=context.default_range,
                portfolio_position=context.portfolio_position,
                options_summary=context.options_summary,
                options_expiration=context.options_expiration,
            )

            response = self._get_llm().complete(prompt)

            # Cache the result with context hash
            self._cache_synthesis(context.ticker, "synthesis_full", response, context_hash)

            return SynthesisResult(
                content=response,
                success=True,
                cached=False
            )

        except Exception as e:
            return SynthesisResult(
                content="",
                success=False,
                error=str(e),
            )

    def generate_from_prompt(self, prompt: str) -> SynthesisResult:
        """Generate synthesis from a custom prompt.

        Args:
            prompt: Custom prompt string

        Returns:
            SynthesisResult with generated content or error
        """
        if not self.health_check():
            return SynthesisResult(
                content="",
                success=False,
                error="LLM service unavailable",
            )

        try:
            response = self._get_llm().complete(prompt)
            return SynthesisResult(
                content=response,
                success=True,
            )
        except Exception as e:
            return SynthesisResult(
                content="",
                success=False,
                error=str(e),
            )

    def evaluate_bank_recommendation(
        self,
        bank_recommendation: str,
        ticker: str,
        ticker_info: dict[str, Any],
        price_range: dict[str, Any],
        analyst_data: dict[str, Any],
        quality_check: dict[str, Any],
        news_sentiment: str,
        strategy_type: str,
    ) -> SynthesisResult:
        """Evaluate a bank recommendation against current research data.

        Args:
            bank_recommendation: The recommendation text from the bank
            ticker: Stock ticker symbol
            ticker_info: Ticker information dict
            price_range: Price range analysis dict
            analyst_data: Analyst data dict
            quality_check: Quality check dict
            news_sentiment: Aggregated news sentiment
            strategy_type: User's strategy type

        Returns:
            SynthesisResult with evaluation or error
        """
        if not self.health_check():
            return SynthesisResult(
                content="",
                success=False,
                error="LLM service unavailable",
            )

        try:
            prompt = build_bank_rec_prompt(
                bank_recommendation=bank_recommendation,
                ticker=ticker,
                ticker_info=ticker_info,
                price_range=price_range,
                analyst_data=analyst_data,
                quality_check=quality_check,
                news_sentiment=news_sentiment,
                strategy_type=strategy_type,
            )

            response = self._get_llm().complete(prompt)

            return SynthesisResult(
                content=response,
                success=True,
            )

        except Exception as e:
            return SynthesisResult(
                content="",
                success=False,
                error=str(e),
            )

    def research_theme(
        self,
        theme: str,
        tax_notes: str,
        risk_tolerance: str,
        margin_rate: float,
        strategy_type: str,
        timeframe: str,
    ) -> SynthesisResult:
        """Research an investment theme.

        Args:
            theme: Investment theme to research
            tax_notes: User's tax considerations
            risk_tolerance: User's risk tolerance level
            margin_rate: Margin rate for dividend arbitrage
            strategy_type: User's strategy type
            timeframe: User's typical timeframe

        Returns:
            SynthesisResult with theme research or error
        """
        if not self.health_check():
            return SynthesisResult(
                content="",
                success=False,
                error="LLM service unavailable",
            )

        try:
            prompt = build_theme_prompt(
                theme=theme,
                tax_notes=tax_notes,
                risk_tolerance=risk_tolerance,
                margin_rate=margin_rate,
                strategy_type=strategy_type,
                timeframe=timeframe,
            )

            response = self._get_llm().complete(prompt)

            return SynthesisResult(
                content=response,
                success=True,
            )

        except Exception as e:
            return SynthesisResult(
                content="",
                success=False,
                error=str(e),
            )
