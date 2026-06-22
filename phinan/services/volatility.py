"""Volatility forecasting service using GARCH models.

Use for: forecasting future volatility, improving range estimates,
assessing if options are cheap/expensive relative to expected vol.
"""

from __future__ import annotations
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

from ..config.settings import settings
from ..models.volatility import GARCHForecast, ExpectedRange, VolatilityComparison


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
            # Use a flag to track if arch was already imported
            import sys
            if 'arch' in sys.modules:
                return True
            import importlib.util
            return importlib.util.find_spec("arch") is not None
        except ImportError:
            return False
        except Exception:
            # Any other error means the service is unavailable
            return False

    def forecast(
        self, returns: pd.Series, horizon: int = 5
    ) -> Union[GARCHForecast, dict]:
        """Forecast volatility using GARCH(1,1).

        Args:
            returns: Series of log returns
            horizon: Forecast horizon in days

        Returns:
            GARCHForecast dataclass on success, dict with error on failure
        """
        if not self._enabled:
            return {"error": "Volatility service disabled", "enabled": False}

        try:
            import numpy as np
            from arch import arch_model

            # Fit GARCH(1,1) model
            model = arch_model(
                returns * 100, vol="Garch", p=1, q=1
            )  # Scale for numerical stability
            fitted = model.fit(disp="off")

            # Generate forecast
            forecast = fitted.forecast(horizon=horizon)

            current_vol = float(fitted.conditional_volatility.iloc[-1]) / 100
            annualized_vol = current_vol * np.sqrt(252)

            return GARCHForecast(
                forecast_variance=forecast.variance.values[-1].tolist(),
                current_volatility=current_vol,
                annualized_vol=annualized_vol,
                horizon_days=horizon,
                model="GARCH(1,1)",
            )
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
    ) -> Union[ExpectedRange, dict]:
        """Calculate expected price range using GARCH forecast.

        Args:
            current_price: Current stock price
            returns: Historical log returns
            days: Forecast horizon
            confidence: Confidence level (0.68 = 1 std dev)

        Returns:
            ExpectedRange dataclass on success, dict with error on failure
        """
        forecast = self.forecast(returns, horizon=days)

        if isinstance(forecast, dict) and "error" in forecast:
            return forecast

        try:
            import numpy as np
            from scipy import stats

            # Get forecast volatility (average over horizon)
            avg_var = np.mean(forecast.forecast_variance) / 10000  # Unscale
            vol = np.sqrt(avg_var * days)  # Scale to horizon

            # Calculate range using normal distribution
            z_score = stats.norm.ppf((1 + confidence) / 2)
            range_pct = z_score * vol

            return ExpectedRange(
                low=current_price * (1 - range_pct),
                high=current_price * (1 + range_pct),
                current=current_price,
                volatility=vol,
                confidence=confidence,
                days=days,
            )
        except Exception as e:
            return {"error": str(e)}

    def compare_to_implied_vol(
        self,
        current_price: float,
        returns: pd.Series,
        implied_vol: float,
        horizon: int = 21,
        confidence: float = 0.68,
    ) -> Union[VolatilityComparison, dict]:
        """Compare GARCH forecast to implied volatility from options.

        Args:
            current_price: Current stock price
            returns: Historical log returns (1 year recommended)
            implied_vol: ATM implied volatility from options (annualized, decimal)
            horizon: Forecast horizon in days
            confidence: Confidence level for range calculation

        Returns:
            VolatilityComparison dataclass on success, dict with error on failure
        """
        if not self._enabled:
            return {"error": "Volatility service disabled", "enabled": False}

        if implied_vol <= 0:
            return {"error": "Invalid implied volatility (must be > 0)"}

        # Get GARCH forecast
        forecast = self.forecast(returns, horizon=horizon)

        if isinstance(forecast, dict) and "error" in forecast:
            return forecast

        # Get expected range
        range_result = self.expected_range(
            current_price, returns, days=horizon, confidence=confidence
        )

        if isinstance(range_result, dict) and "error" in range_result:
            return range_result

        # Calculate comparison metrics
        garch_vol = forecast.annualized_vol
        ratio = implied_vol / garch_vol if garch_vol > 0 else 0
        diff = implied_vol - garch_vol

        return VolatilityComparison(
            garch_annualized_vol=garch_vol,
            implied_vol=implied_vol,
            forecast_horizon_days=horizon,
            iv_garch_ratio=ratio,
            iv_garch_diff=diff,
            expected_range_low=range_result.low,
            expected_range_high=range_result.high,
        )
