"""Volatility-specific child state for the Research module."""

import reflex as rx

from .state import ResearchState


class VolatilityState(ResearchState):
    """Own GARCH and implied-volatility comparison state."""

    volatility_garch_vol: float = 0.0
    volatility_implied_vol: float = 0.0
    volatility_iv_garch_ratio: float = 0.0
    volatility_iv_garch_diff: float = 0.0
    volatility_range_low: float = 0.0
    volatility_range_high: float = 0.0
    volatility_horizon: str = "21"
    volatility_available: bool = False
    volatility_error: str = ""
    volatility_loading: bool = False

    # Volatility computed vars
    @rx.var
    def volatility_garch_vol_pct(self) -> str:
        """GARCH volatility formatted as percentage."""
        return (
            f"{self.volatility_garch_vol * 100:.1f}%"
            if self.volatility_garch_vol
            else "N/A"
        )

    @rx.var
    def volatility_implied_vol_pct(self) -> str:
        """Implied volatility formatted as percentage."""
        return (
            f"{self.volatility_implied_vol * 100:.1f}%"
            if self.volatility_implied_vol
            else "N/A"
        )

    @rx.var
    def volatility_iv_garch_ratio_fmt(self) -> str:
        """IV/GARCH ratio formatted."""
        return (
            f"{self.volatility_iv_garch_ratio:.2f}x"
            if self.volatility_iv_garch_ratio
            else "N/A"
        )

    @rx.var
    def volatility_iv_garch_diff_pct(self) -> str:
        """IV-GARCH difference formatted as percentage points."""
        if self.volatility_iv_garch_diff:
            sign = "+" if self.volatility_iv_garch_diff > 0 else ""
            return f"{sign}{self.volatility_iv_garch_diff * 100:.1f}pp"
        return "N/A"

    @rx.var
    def volatility_interpretation(self) -> str:
        """Human-readable interpretation of IV vs GARCH."""
        if not self.volatility_available or self.volatility_iv_garch_ratio == 0:
            return ""
        if self.volatility_iv_garch_ratio > 1.15:
            return "IV premium - options may be expensive"
        elif self.volatility_iv_garch_ratio < 0.85:
            return "IV discount - options may be cheap"
        else:
            return "IV near fair value"

    @rx.var
    def volatility_interpretation_color(self) -> str:
        """Color scheme for volatility interpretation."""
        if not self.volatility_available or self.volatility_iv_garch_ratio == 0:
            return "gray"
        if self.volatility_iv_garch_ratio > 1.15:
            return "amber"  # Expensive
        elif self.volatility_iv_garch_ratio < 0.85:
            return "green"  # Cheap
        else:
            return "blue"  # Fair

    @rx.var
    def volatility_horizon_label(self) -> str:
        """Human-readable horizon label."""
        horizon_map = {"5": "1 Week", "21": "1 Month", "63": "3 Months"}
        return horizon_map.get(self.volatility_horizon, "1 Month")

    async def _fetch_volatility_data_safe(self, options_atm_iv: float) -> None:
        """Compute volatility while converting unexpected errors to state."""
        try:
            await self._fetch_volatility_data(options_atm_iv)
        except Exception as e:
            self.volatility_error = str(e)
            self.volatility_available = False

    async def set_volatility_horizon(self, horizon: str):
        """Set the horizon and recompute from the current options snapshot."""
        from .options_state import OptionsState

        self.volatility_horizon = horizon
        options_state = await self.get_state(OptionsState)
        await self._fetch_volatility_data(options_state.options_atm_iv)

    async def _fetch_volatility_data(self, options_atm_iv: float):
        """Fetch and compute volatility analysis data.

        Requires:
        - Ticker selected
        - Options data loaded (for ATM IV)
        - Price history available

        Uses 1 year of price history for GARCH accuracy.
        """
        from ...services import services

        if not self.selected_ticker:
            return

        # Need ATM IV from options
        if options_atm_iv <= 0:
            self.volatility_error = "ATM IV not available"
            self.volatility_available = False
            return

        # Check if volatility service is available
        if not services.volatility.health_check():
            self.volatility_error = "Volatility service disabled or unavailable"
            self.volatility_available = False
            return

        try:
            self.volatility_loading = True
            self.volatility_error = ""

            # Get current price
            current_price = self.ticker_info.get("current_price", 0)
            if not current_price:
                self.volatility_error = "Current price not available"
                self.volatility_available = False
                return

            # Fetch 1 year of price history for GARCH accuracy
            df = services.market_data.get_price_history(
                self.selected_ticker, period="1y", interval="1d"
            )

            if df.empty or len(df) < 60:  # Need at least 60 days
                self.volatility_error = "Insufficient price history for GARCH"
                self.volatility_available = False
                return

            # Calculate log returns (lazy import to reduce startup memory)
            import numpy as np

            # Case-insensitive column access
            col_map = {c.lower(): c for c in df.columns}
            close_col = col_map.get("close")

            if not close_col:
                self.volatility_error = "Close price column not found"
                self.volatility_available = False
                return

            close_prices = df[close_col]
            returns = np.log(close_prices / close_prices.shift(1)).dropna()

            # Get horizon from state (string to int)
            horizon = int(self.volatility_horizon)

            # Run volatility comparison
            result = services.volatility.compare_to_implied_vol(
                current_price=current_price,
                returns=returns,
                implied_vol=options_atm_iv,
                horizon=horizon,
                confidence=0.68,
            )

            # Check for error
            if isinstance(result, dict) and "error" in result:
                self.volatility_error = result["error"]
                self.volatility_available = False
                return

            # Store results
            self.volatility_garch_vol = result.garch_annualized_vol
            self.volatility_implied_vol = result.implied_vol
            self.volatility_iv_garch_ratio = result.iv_garch_ratio
            self.volatility_iv_garch_diff = result.iv_garch_diff
            self.volatility_range_low = result.expected_range_low
            self.volatility_range_high = result.expected_range_high
            self.volatility_available = True

        except Exception as e:
            self.volatility_error = f"Error computing volatility: {str(e)}"
            self.volatility_available = False
        finally:
            self.volatility_loading = False

    def _reset_volatility(self) -> None:
        """Reset all volatility-owned state."""
        self.volatility_garch_vol = 0.0
        self.volatility_implied_vol = 0.0
        self.volatility_iv_garch_ratio = 0.0
        self.volatility_iv_garch_diff = 0.0
        self.volatility_range_low = 0.0
        self.volatility_range_high = 0.0
        self.volatility_horizon = "21"
        self.volatility_available = False
        self.volatility_error = ""
        self.volatility_loading = False

