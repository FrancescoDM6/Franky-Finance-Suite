"""Health check API endpoint.

Provides comprehensive health status for all services:
- Database (DuckDB)
- LLM (Gemini primary, Ollama fallback)
- Market Data (yfinance)
- AI Services (sentiment, volatility, embeddings)
"""

import time
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    """Status of an individual service."""

    name: str
    status: str  # "healthy", "unhealthy", "disabled", "degraded"
    response_time_ms: float | None = None
    details: dict[str, Any] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Complete health check response."""

    status: str  # "healthy", "unhealthy", "degraded"
    timestamp: str
    version: str = "1.0.0"
    services: list[ServiceStatus]
    summary: dict[str, int]


def check_database() -> ServiceStatus:
    """Check DuckDB database connectivity."""
    start = time.perf_counter()
    try:
        from ..services import services

        healthy = services.db.health_check()
        elapsed = (time.perf_counter() - start) * 1000

        if healthy:
            # Get additional info
            schema_version = services.db.get_schema_version()
            return ServiceStatus(
                name="database",
                status="healthy",
                response_time_ms=round(elapsed, 2),
                details={
                    "type": "DuckDB",
                    "schema_version": schema_version,
                },
            )
        else:
            return ServiceStatus(
                name="database",
                status="unhealthy",
                response_time_ms=round(elapsed, 2),
                error="Database connection failed",
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="database",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=str(e),
        )


def check_ollama() -> ServiceStatus:
    """Check Ollama LLM connectivity."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        import ollama

        client = ollama.Client(host=settings.ollama.base_url)
        models = client.list()
        elapsed = (time.perf_counter() - start) * 1000

        model_names = [m.get("name", m.get("model", "unknown")) for m in models.get("models", [])]

        return ServiceStatus(
            name="ollama",
            status="healthy",
            response_time_ms=round(elapsed, 2),
            details={
                "base_url": settings.ollama.base_url,
                "default_model": settings.ollama.model,
                "available_models": model_names[:5],  # Limit to 5
            },
        )
    except ImportError:
        return ServiceStatus(
            name="ollama",
            status="unhealthy",
            error="ollama package not installed",
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="ollama",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=f"Connection failed: {str(e)[:100]}",
        )


def check_gemini() -> ServiceStatus:
    """Check Gemini API connectivity."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings

        if not settings.gemini.api_key:
            return ServiceStatus(
                name="gemini",
                status="disabled",
                details={"reason": "No API key configured"},
            )

        from google import genai

        client = genai.Client(api_key=settings.gemini.api_key)
        # Quick validation - list models (lightweight call)
        models = list(client.models.list())
        elapsed = (time.perf_counter() - start) * 1000

        return ServiceStatus(
            name="gemini",
            status="healthy",
            response_time_ms=round(elapsed, 2),
            details={
                "configured_model": settings.gemini.model,
                "available_models": len(models),
            },
        )
    except ImportError:
        return ServiceStatus(
            name="gemini",
            status="unhealthy",
            error="google-genai package not installed",
        )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        error_msg = str(e)[:100]

        # Check for rate limit
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return ServiceStatus(
                name="gemini",
                status="degraded",
                response_time_ms=round(elapsed, 2),
                details={"reason": "Rate limited"},
                error="API rate limit reached",
            )

        return ServiceStatus(
            name="gemini",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=error_msg,
        )


def check_market_data() -> ServiceStatus:
    """Check yfinance API connectivity."""
    start = time.perf_counter()
    try:
        from ..services import services

        # Test with a known stable ticker
        info = services.market_data.get_ticker_info("AAPL")
        elapsed = (time.perf_counter() - start) * 1000

        if info and info.current_price:
            return ServiceStatus(
                name="market_data",
                status="healthy",
                response_time_ms=round(elapsed, 2),
                details={
                    "provider": "yfinance",
                    "test_ticker": "AAPL",
                    "test_price": info.current_price,
                },
            )
        else:
            return ServiceStatus(
                name="market_data",
                status="degraded",
                response_time_ms=round(elapsed, 2),
                details={"provider": "yfinance"},
                error="Could not fetch ticker data",
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="market_data",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=str(e)[:100],
        )


def check_sentiment() -> ServiceStatus:
    """Check FinBERT sentiment service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_sentiment:
            return ServiceStatus(
                name="sentiment",
                status="disabled",
                details={"reason": "Service disabled in config"},
            )

        # Check if service reports healthy (without loading model)
        healthy = services.sentiment.health_check()
        elapsed = (time.perf_counter() - start) * 1000

        if healthy:
            return ServiceStatus(
                name="sentiment",
                status="healthy",
                response_time_ms=round(elapsed, 2),
                details={
                    "model": settings.ai_services.sentiment_model,
                    "loaded": services.sentiment._model is not None,
                },
            )
        else:
            return ServiceStatus(
                name="sentiment",
                status="unhealthy",
                response_time_ms=round(elapsed, 2),
                error="Service health check failed",
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="sentiment",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=str(e)[:100],
        )


def check_volatility() -> ServiceStatus:
    """Check GARCH volatility service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_volatility:
            return ServiceStatus(
                name="volatility",
                status="disabled",
                details={"reason": "Service disabled in config"},
            )

        healthy = services.volatility.health_check()
        elapsed = (time.perf_counter() - start) * 1000

        if healthy:
            return ServiceStatus(
                name="volatility",
                status="healthy",
                response_time_ms=round(elapsed, 2),
                details={"model": "GARCH(1,1)"},
            )
        else:
            return ServiceStatus(
                name="volatility",
                status="unhealthy",
                response_time_ms=round(elapsed, 2),
                error="arch package not available",
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="volatility",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=str(e)[:100],
        )


def check_embeddings() -> ServiceStatus:
    """Check sentence-transformers embedding service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_embeddings:
            return ServiceStatus(
                name="embeddings",
                status="disabled",
                details={"reason": "Service disabled in config"},
            )

        healthy = services.embeddings.health_check()
        elapsed = (time.perf_counter() - start) * 1000

        if healthy:
            return ServiceStatus(
                name="embeddings",
                status="healthy",
                response_time_ms=round(elapsed, 2),
                details={
                    "model": settings.ai_services.embedding_model,
                    "loaded": services.embeddings._model is not None,
                },
            )
        else:
            return ServiceStatus(
                name="embeddings",
                status="unhealthy",
                response_time_ms=round(elapsed, 2),
                error="Service health check failed",
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            name="embeddings",
            status="unhealthy",
            response_time_ms=round(elapsed, 2),
            error=str(e)[:100],
        )


def get_health_status() -> HealthResponse:
    """Run all health checks and return comprehensive status."""
    services_status = [
        check_database(),
        check_gemini(),
        check_ollama(),
        check_market_data(),
        check_sentiment(),
        check_volatility(),
        check_embeddings(),
    ]

    # Calculate summary
    summary = {
        "healthy": sum(1 for s in services_status if s.status == "healthy"),
        "unhealthy": sum(1 for s in services_status if s.status == "unhealthy"),
        "degraded": sum(1 for s in services_status if s.status == "degraded"),
        "disabled": sum(1 for s in services_status if s.status == "disabled"),
    }

    # Determine overall status
    # Critical services: database, at least one LLM (gemini or ollama)
    db_status = next(s for s in services_status if s.name == "database")
    gemini_status = next(s for s in services_status if s.name == "gemini")
    ollama_status = next(s for s in services_status if s.name == "ollama")

    db_ok = db_status.status == "healthy"
    llm_ok = gemini_status.status == "healthy" or ollama_status.status == "healthy"

    if not db_ok:
        overall = "unhealthy"
    elif not llm_ok:
        overall = "unhealthy"
    elif summary["unhealthy"] > 0 or summary["degraded"] > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthResponse(
        status=overall,
        timestamp=datetime.utcnow().isoformat() + "Z",
        services=services_status,
        summary=summary,
    )


# Create FastAPI app for health endpoints
health_api = FastAPI(
    title="Phinan Health API",
    description="Health check endpoints for Phinan Finance Suite",
    version="1.0.0",
)


@health_api.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check for all services."""
    return get_health_status()


@health_api.get("/health/live")
async def liveness():
    """Simple liveness probe - returns 200 if app is running."""
    return {"status": "alive"}


@health_api.get("/health/ready")
async def readiness():
    """Readiness probe - checks critical services only."""
    db = check_database()
    gemini = check_gemini()
    ollama = check_ollama()

    # Ready if DB works and at least one LLM is available
    db_ok = db.status == "healthy"
    llm_ok = gemini.status == "healthy" or ollama.status == "healthy"

    if db_ok and llm_ok:
        return {"status": "ready", "database": db.status, "llm": "available"}
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": db.status,
                "gemini": gemini.status,
                "ollama": ollama.status,
            },
        )
