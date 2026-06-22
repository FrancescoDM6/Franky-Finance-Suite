"""Volatility data models.

Contains:
- Dataclasses for service layer (GARCHForecast, ExpectedRange, VolatilityComparison)
- Pydantic model for Reflex state (VolatilityData)
- Constants for horizon options (FORECAST_HORIZONS)
"""

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class GARCHForecast:
    """GARCH(1,1) volatility forecast result.

    Used by VolatilityService.forecast() to return typed results.
    """

    forecast_variance: list[float]
    current_volatility: float  # Daily volatility (decimal)
    annualized_vol: float  # Annualized volatility (decimal)
    horizon_days: int
    model: str = "GARCH(1,1)"


@dataclass
class ExpectedRange:
    """Expected price range based on GARCH forecast.

    Used by VolatilityService.expected_range() to return typed results.
    """

    low: float
    high: float
    current: float
    volatility: float  # Scaled to horizon
    confidence: float  # e.g., 0.68 for 1 std dev
    days: int


@dataclass
class VolatilityComparison:
    """Comparison of GARCH forecast vs implied volatility.

    Used by VolatilityService.compare_to_implied_vol() to return typed results.
    """

    garch_annualized_vol: float  # GARCH forecast (annualized, decimal)
    implied_vol: float  # ATM IV from options (annualized, decimal)
    forecast_horizon_days: int
    iv_garch_ratio: float  # IV / GARCH (>1 means IV premium)
    iv_garch_diff: float  # IV - GARCH (positive = IV higher)
    expected_range_low: float
    expected_range_high: float

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation of the comparison."""
        if self.iv_garch_ratio > 1.15:
            return "IV premium - options may be expensive"
        elif self.iv_garch_ratio < 0.85:
            return "IV discount - options may be cheap"
        else:
            return "IV near fair value"


class VolatilityData(BaseModel):
    """Pydantic model for Reflex state serialization.

    Used in ResearchState to store volatility analysis data.
    Pydantic BaseModel is required for proper Reflex state serialization.
    """

    garch_vol: float = 0.0  # Annualized GARCH volatility (decimal)
    implied_vol: float = 0.0  # ATM IV (decimal)
    iv_garch_ratio: float = 0.0  # IV / GARCH ratio
    iv_garch_diff: float = 0.0  # IV - GARCH difference
    range_low: float = 0.0  # Expected range low price
    range_high: float = 0.0  # Expected range high price
    horizon_days: int = 21  # Forecast horizon in days
    is_available: bool = False  # Whether data is valid
    error: str = ""  # Error message if any


# Forecast horizon options for UI dropdown
FORECAST_HORIZONS = [
    {"value": "5", "label": "1 Week (5 days)"},
    {"value": "21", "label": "1 Month (21 days)"},
    {"value": "63", "label": "3 Months (63 days)"},
]
