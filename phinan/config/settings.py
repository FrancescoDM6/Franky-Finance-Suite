"""Application settings with environment variable support.

Uses Pydantic for validation and environment variable loading.
All settings can be overridden via PHINAN_ prefixed environment variables.
"""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="PHINAN_DATABASE_")

    path: str = Field(
        default="~/.phinan/phinan.duckdb",
        description="Path to DuckDB database file",
    )

    @property
    def resolved_path(self) -> Path:
        """Get resolved database path."""
        return Path(self.path).expanduser()


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration."""

    model_config = SettingsConfigDict(env_prefix="PHINAN_OLLAMA_")

    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    model: str = Field(
        default="llama3.2:latest",
        description="Default model for chat completions",
    )
    timeout: int = Field(
        default=120,
        description="Request timeout in seconds",
    )


class AIServicesSettings(BaseSettings):
    """AI services configuration."""

    model_config = SettingsConfigDict(env_prefix="PHINAN_AI_SERVICES_")

    sentiment_model: str = Field(
        default="yiyanghkust/finbert-tone",
        description="FinBERT model for sentiment analysis",
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Model for text embeddings",
    )
    enable_sentiment: bool = Field(
        default=False,
        description="Enable sentiment analysis service",
    )
    enable_volatility: bool = Field(
        default=False,
        description="Enable GARCH volatility forecasting",
    )
    enable_embeddings: bool = Field(
        default=False,
        description="Enable embedding service for similarity search",
    )


class MarketDataSettings(BaseSettings):
    """Market data provider configuration."""

    model_config = SettingsConfigDict(env_prefix="PHINAN_MARKET_DATA_")

    provider: str = Field(
        default="yfinance",
        description="Market data provider (yfinance or polygon)",
    )
    cache_ttl_minutes: int = Field(
        default=5,
        description="Cache TTL for market data",
    )
    rate_limit_delay: float = Field(
        default=0.5,
        description="Delay between API calls in seconds",
    )


class AssistantSettings(BaseSettings):
    """Assistant configuration."""

    model_config = SettingsConfigDict(env_prefix="PHINAN_ASSISTANT_")

    max_context_messages: int = Field(
        default=50,
        description="Maximum messages to keep in context",
    )
    context_window: int = Field(
        default=4096,
        description="Token context window size",
    )


class Settings(BaseSettings):
    """Root application settings."""

    model_config = SettingsConfigDict(
        env_prefix="PHINAN_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    debug: bool = Field(default=False, description="Debug mode")
    app_name: str = Field(default="Phinan Finance Suite")

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    ai_services: AIServicesSettings = Field(default_factory=AIServicesSettings)
    market_data: MarketDataSettings = Field(default_factory=MarketDataSettings)
    assistant: AssistantSettings = Field(default_factory=AssistantSettings)


# Global settings instance
settings = Settings()
