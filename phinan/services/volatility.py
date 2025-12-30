"""Volatility forecasting service using GARCH models.

Use for: forecasting future volatility, improving range estimates,
assessing if options are cheap/expensive relative to expected vol.
"""

from typing import Optional

import pandas as pd

from ..config.settings import settings


class VolatilityService:
    """GARCH-based volatility forecasting service."""

    def __init__(self):
        """Initialize volatility service."""
        self._enabled = settings.ai_services.enable_volatility

    def health_check(self) -> bool:
        """Check if volatility service is available."""
        if not self._enabled:
            return False
        try:
            import arch

            return True
        except ImportError:
            return False

    def forecast(self, returns: pd.Series, horizon: int = 5) -> dict:
        """Forecast volatility using GARCH(1,1).

        Args:
            returns: Series of log returns
            horizon: Forecast horizon in days

        Returns:
            Dict with forecast variance and current volatility
        """
        if not self._enabled:
            return {"error": "Volatility service disabled", "enabled": False}

        try:
            from arch import arch_model

            # Fit GARCH(1,1) model
            model = arch_model(returns * 100, vol="Garch", p=1, q=1)  # Scale for numerical stability
            fitted = model.fit(disp="off")

            # Generate forecast
            forecast = fitted.forecast(horizon=horizon)

            return {
                "forecast_variance": forecast.variance.values[-1].tolist(),
                "current_volatility": float(fitted.conditional_volatility[-1]) / 100,
                "annualized_vol": float(fitted.conditional_volatility[-1]) / 100 * (252**0.5),
                "model": "GARCH(1,1)",
            }
        except ImportError:
            return {"error": "arch package not installed. Run: pip install arch"}
        except Exception as e:
            return {"error": str(e)}

    def expected_range(
        self,
        current_price: float,
        returns: pd.Series,
        days: int = 5,
        confidence: float = 0.68,
    ) -> dict:
        """Calculate expected price range using GARCH forecast.

        Args:
            current_price: Current stock price
            returns: Historical log returns
            days: Forecast horizon
            confidence: Confidence level (0.68 = 1 std dev)

        Returns:
            Dict with expected range bounds
        """
        forecast = self.forecast(returns, horizon=days)

        if "error" in forecast:
            return forecast

        try:
            import numpy as np
            from scipy import stats

            # Get forecast volatility (average over horizon)
            avg_var = np.mean(forecast["forecast_variance"]) / 10000  # Unscale
            vol = np.sqrt(avg_var * days)  # Scale to horizon

            # Calculate range using normal distribution
            z_score = stats.norm.ppf((1 + confidence) / 2)
            range_pct = z_score * vol

            return {
                "low": current_price * (1 - range_pct),
                "high": current_price * (1 + range_pct),
                "current": current_price,
                "volatility": vol,
                "confidence": confidence,
                "days": days,
            }
        except Exception as e:
            return {"error": str(e)}
