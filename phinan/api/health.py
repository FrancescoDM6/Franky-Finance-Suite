"""Health check API endpoint.

Provides comprehensive health status for all services:
- Database (DuckDB)
- LLM (Gemini primary, Ollama fallback)
- Market Data (yfinance)
- AI Services (sentiment, volatility, embeddings)
"""

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel


HEALTH_CHECK_TICKER = "AAPL"


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


def _elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds rounded for the public response."""
    return round((time.perf_counter() - started_at) * 1000, 2)


def _service_status(
    name: str,
    status: str,
    *,
    started_at: float | None = None,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> ServiceStatus:
    """Construct a service status with optional elapsed timing."""
    response_time_ms = _elapsed_ms(started_at) if started_at is not None else None
    return ServiceStatus(
        name=name,
        status=status,
        response_time_ms=response_time_ms,
        details=details,
        error=error,
    )


def check_database() -> ServiceStatus:
    """Check DuckDB database connectivity."""
    start = time.perf_counter()
    try:
        from ..services import services

        healthy = services.db.health_check()
        if healthy:
            # Get additional info
            schema_version = services.db.get_schema_version()
            return _service_status(
                "database",
                "healthy",
                started_at=start,
                details={
                    "type": "DuckDB",
                    "schema_version": schema_version,
                },
            )
        return _service_status(
            "database",
            "unhealthy",
            started_at=start,
            error="Database connection failed",
        )
    except Exception as exc:
        return _service_status(
            "database", "unhealthy", started_at=start, error=str(exc)
        )


def check_ollama() -> ServiceStatus:
    """Check Ollama LLM connectivity."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        import ollama

        client = ollama.Client(host=settings.ollama.base_url)
        models = client.list()
        model_names = [
            m.get("name", m.get("model", "unknown")) for m in models.get("models", [])
        ]

        return _service_status(
            "ollama",
            "healthy",
            started_at=start,
            details={
                "base_url": settings.ollama.base_url,
                "default_model": settings.ollama.model,
                "available_models": model_names[:5],  # Limit to 5
            },
        )
    except ImportError:
        return _service_status(
            "ollama", "unhealthy", error="ollama package not installed"
        )
    except Exception as exc:
        return _service_status(
            "ollama",
            "unhealthy",
            started_at=start,
            error=f"Connection failed: {str(exc)[:100]}",
        )


def check_gemini() -> ServiceStatus:
    """Check Gemini API connectivity."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings

        if not settings.gemini.api_key:
            return _service_status(
                "gemini",
                "disabled",
                details={"reason": "No API key configured"},
            )

        from google import genai

        from ..services.circuit_breaker import with_timeout

        client = genai.Client(api_key=settings.gemini.api_key)
        # Quick validation - list models (lightweight call). Bounded so a
        # slow Gemini API cannot hang the readiness probe.
        models = with_timeout(lambda: list(client.models.list()), 5.0)

        return _service_status(
            "gemini",
            "healthy",
            started_at=start,
            details={
                "configured_model": settings.gemini.model,
                "available_models": len(models),
            },
        )
    except ImportError:
        return _service_status(
            "gemini", "unhealthy", error="google-genai package not installed"
        )
    except TimeoutError:
        return _service_status(
            "gemini",
            "degraded",
            started_at=start,
            details={"reason": "API slow to respond"},
            error="Model list timed out after 5s",
        )
    except Exception as exc:
        error_msg = str(exc)[:100]

        # Check for rate limit
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return _service_status(
                "gemini",
                "degraded",
                started_at=start,
                details={"reason": "Rate limited"},
                error="API rate limit reached",
            )

        return _service_status(
            "gemini",
            "unhealthy",
            started_at=start,
            error=error_msg,
        )


def check_market_data() -> ServiceStatus:
    """Check yfinance API connectivity."""
    start = time.perf_counter()
    try:
        from ..services import services

        # The probe ticker is centralized configuration for this health check.
        info = services.market_data.get_ticker_info(HEALTH_CHECK_TICKER)

        if info and info.current_price:
            return _service_status(
                "market_data",
                "healthy",
                started_at=start,
                details={
                    "provider": "yfinance",
                    "test_ticker": HEALTH_CHECK_TICKER,
                    "test_price": info.current_price,
                },
            )
        return _service_status(
            "market_data",
            "degraded",
            started_at=start,
            details={"provider": "yfinance"},
            error="Could not fetch ticker data",
        )
    except Exception as exc:
        return _service_status(
            "market_data",
            "unhealthy",
            started_at=start,
            error=str(exc)[:100],
        )


def check_sentiment() -> ServiceStatus:
    """Check FinBERT sentiment service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_sentiment:
            return _service_status(
                "sentiment",
                "disabled",
                details={"reason": "Service disabled in config"},
            )

        # Check if service reports healthy (without loading model)
        healthy = services.sentiment.health_check()

        if healthy:
            return _service_status(
                "sentiment",
                "healthy",
                started_at=start,
                details={
                    "model": settings.ai_services.sentiment_model,
                    "loaded": services.sentiment._model is not None,
                },
            )
        return _service_status(
            "sentiment",
            "unhealthy",
            started_at=start,
            error="Service health check failed",
        )
    except Exception as exc:
        return _service_status(
            "sentiment",
            "unhealthy",
            started_at=start,
            error=str(exc)[:100],
        )


def check_volatility() -> ServiceStatus:
    """Check GARCH volatility service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_volatility:
            return _service_status(
                "volatility",
                "disabled",
                details={"reason": "Service disabled in config"},
            )

        healthy = services.volatility.health_check()

        if healthy:
            return _service_status(
                "volatility",
                "healthy",
                started_at=start,
                details={"model": "GARCH(1,1)"},
            )
        return _service_status(
            "volatility",
            "unhealthy",
            started_at=start,
            error="arch package not available",
        )
    except Exception as exc:
        return _service_status(
            "volatility",
            "unhealthy",
            started_at=start,
            error=str(exc)[:100],
        )


def check_embeddings() -> ServiceStatus:
    """Check sentence-transformers embedding service."""
    start = time.perf_counter()
    try:
        from ..config.settings import settings
        from ..services import services

        if not settings.ai_services.enable_embeddings:
            return _service_status(
                "embeddings",
                "disabled",
                details={"reason": "Service disabled in config"},
            )

        healthy = services.embeddings.health_check()

        if healthy:
            return _service_status(
                "embeddings",
                "healthy",
                started_at=start,
                details={
                    "model": settings.ai_services.embedding_model,
                    "loaded": services.embeddings._model is not None,
                },
            )
        return _service_status(
            "embeddings",
            "unhealthy",
            started_at=start,
            error="Service health check failed",
        )
    except Exception as exc:
        return _service_status(
            "embeddings",
            "unhealthy",
            started_at=start,
            error=str(exc)[:100],
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
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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


@health_api.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint for scraping."""
    from fastapi.responses import Response
    from ..core.metrics import metrics

    content = metrics.generate_latest()
    return Response(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
