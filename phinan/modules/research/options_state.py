"""Options-specific child state for the Research module."""

import logging

import reflex as rx

from .research_cache import LRUCache
from .state import ResearchState

logger = logging.getLogger(__name__)

_options_cache = LRUCache()


class OptionsState(ResearchState):
    """Own options-chain state and presentation data."""

    options_expirations: list[str] = []
    selected_expiration: str = ""
    options_calls: list[dict] = []
    options_puts: list[dict] = []
    options_atm_iv: float = 0.0
    options_days_to_expiry: int = 0
    options_loading: bool = False
    options_error: str = ""
    options_summary: str = ""

    @rx.var
    def options_atm_iv_pct(self) -> str:
        """ATM IV formatted as percentage."""
        return f"{self.options_atm_iv * 100:.1f}%" if self.options_atm_iv else "N/A"

    @rx.var
    def options_expiry_label(self) -> str:
        """Human-readable expiration label with days remaining."""
        if not self.selected_expiration:
            return "Select Expiration"
        return f"{self.selected_expiration} ({self.options_days_to_expiry}d)"

    @rx.var
    def has_options_data(self) -> bool:
        """Whether options data is loaded."""
        return len(self.options_calls) > 0 or len(self.options_puts) > 0

    async def set_options_expiration(self, expiration: str):
        """Load a newly selected options expiration."""
        self.selected_expiration = expiration
        await self._load_options_for_expiration()

    async def _fetch_options_data(self):
        """Fetch and process options chain data for current ticker.

        Loads all expirations, selects profile-appropriate default,
        and processes interesting strikes with annotations.
        """
        from ...services import services
        from ...state.user_context import UserContextState

        if not self.selected_ticker:
            return

        try:
            self.options_loading = True
            self.options_error = ""

            # Get user profile for default selection
            user_ctx = await self.get_state(UserContextState)

            # Fetch all expirations
            expirations = await services.market_data.get_options_expirations_async(
                self.selected_ticker
            )

            if not expirations:
                self.options_expirations = []
                self.selected_expiration = ""
                self.options_calls = []
                self.options_puts = []
                self.options_atm_iv = 0.0
                self.options_days_to_expiry = 0
                self.options_error = "No options listed for this ticker."
                self.options_summary = "No options listed."
                return

            self.options_expirations = expirations

            # Select default expiration based on profile
            default_exp = self._get_default_expiration_for_profile(
                expirations, user_ctx.typical_timeframe
            )
            self.selected_expiration = default_exp

            # Load options for the default expiration
            await self._load_options_for_expiration()

        except Exception as e:
            logger.error("Error fetching options for %s: %s", self.selected_ticker, e)
            self.options_expirations = []
            self.selected_expiration = ""
            self.options_calls = []
            self.options_puts = []
            self.options_atm_iv = 0.0
            self.options_days_to_expiry = 0
            self.options_error = f"Error fetching options: {str(e)}"
            self.options_summary = "Error fetching options data."
        finally:
            self.options_loading = False

    def _get_default_expiration_for_profile(
        self, expirations: list[str], profile_timeframe: str
    ) -> str:
        """Select the best default expiration based on user profile.

        - Conservative (2_weeks): First expiration in 7-21 day range
        - Aggressive (1_2_months): First expiration in 30-60 day range
        - Standard (varies): First available expiration

        Falls back to first expiration if no match in preferred range.
        """
        from datetime import datetime

        if not expirations:
            return ""

        today = datetime.now().date()

        # Define target ranges based on profile
        if profile_timeframe == "1_week":
            min_days, max_days = 3, 10
        elif profile_timeframe == "2_weeks":
            min_days, max_days = 7, 21
        elif profile_timeframe == "1_2_months":
            min_days, max_days = 30, 60
        else:
            # Standard or default: just use first expiration
            return expirations[0]

        # Find first expiration in target range
        for exp_str in expirations:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                days_out = (exp_date - today).days

                if min_days <= days_out <= max_days:
                    return exp_str
            except ValueError:
                continue

        # No match in preferred range - fallback to first expiration
        return expirations[0]

    async def _load_options_for_expiration(self):
        """Load and filter options chain for selected expiration.

        Uses cached data if available and not expired (5 min TTL).
        """
        from ...services import services
        from datetime import datetime

        if not self.selected_expiration or not self.selected_ticker:
            return

        try:
            self.options_loading = True

            # Calculate days to expiry
            exp_date = datetime.strptime(self.selected_expiration, "%Y-%m-%d").date()
            today = datetime.now().date()
            self.options_days_to_expiry = (exp_date - today).days

            # Check LRU cache first (bounded memory, TTL-aware)
            cache_key = f"{self.selected_ticker}:{self.selected_expiration}"
            cached_chain = _options_cache.get(cache_key)

            if cached_chain is not None:
                # Use cached data (TTL already checked by LRUCache)
                chain = cached_chain
            else:
                # Fetch fresh data
                chain = await services.market_data.get_options_chain_async(
                    self.selected_ticker, self.selected_expiration
                )
                # Cache it (LRUCache handles eviction automatically)
                _options_cache.set(cache_key, chain)

            calls_df = chain.get("calls")
            puts_df = chain.get("puts")

            if calls_df is None or calls_df.empty:
                self.options_calls = []
                self.options_puts = []
                self.options_atm_iv = 0.0
                self._build_structured_options_summary()
                return

            # Get reference prices for filtering
            current_price = self.ticker_info.get("current_price", 0)
            range_high = self.price_range.get("high", 0)
            range_low = self.price_range.get("low", 0)
            target_price = self.analyst_data.get("target_price", 0)

            # Get interesting strikes
            all_strikes = sorted(calls_df["strike"].unique().tolist())
            interesting = self._get_interesting_strikes(
                all_strikes, current_price, range_high, range_low, target_price
            )

            strike_info = {s["strike"]: s for s in interesting}
            interesting_strikes = list(strike_info.keys())

            # Filter and format calls
            self.options_calls = self._format_options_rows(
                calls_df, interesting_strikes, strike_info, "call"
            )

            # Filter and format puts
            self.options_puts = self._format_options_rows(
                puts_df, interesting_strikes, strike_info, "put"
            )

            # Calculate ATM IV (average of ATM call and put IV)
            atm_strike = next((s["strike"] for s in interesting if s["is_atm"]), None)
            if atm_strike:
                ivs = []
                atm_call = calls_df[calls_df["strike"] == atm_strike]
                atm_put = puts_df[puts_df["strike"] == atm_strike]
                if not atm_call.empty and "impliedVolatility" in atm_call.columns:
                    iv = atm_call.iloc[0]["impliedVolatility"]
                    if iv and iv > 0:
                        ivs.append(iv)
                if not atm_put.empty and "impliedVolatility" in atm_put.columns:
                    iv = atm_put.iloc[0]["impliedVolatility"]
                    if iv and iv > 0:
                        ivs.append(iv)
                self.options_atm_iv = sum(ivs) / len(ivs) if ivs else 0
            else:
                self.options_atm_iv = 0.0

            # Build structured summary for LLM
            self._build_structured_options_summary()

        except Exception as e:
            logger.error(
                "Error loading options chain for %s/%s: %s",
                self.selected_ticker,
                self.selected_expiration,
                e,
            )
            self.options_calls = []
            self.options_puts = []
            self.options_atm_iv = 0.0
            self.options_error = f"Error loading chain: {str(e)}"
        finally:
            self.options_loading = False

    def _get_interesting_strikes(
        self,
        strikes: list[float],
        current_price: float,
        range_high: float,
        range_low: float,
        target_price: float,
    ) -> list[dict]:
        """Filter to 'interesting' strikes with annotations.

        Returns list of dicts: {strike, annotation, is_atm}
        """
        if not strikes or not current_price:
            return []

        interesting = []
        seen_strikes = set()

        # Define bounds: +/- 10% of current price
        lower_bound = current_price * 0.90
        upper_bound = current_price * 1.10

        # Find ATM strike (closest to current price)
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))

        # Find round number interval
        round_interval = 5 if current_price < 100 else 10

        for strike in sorted(strikes):
            if strike < lower_bound or strike > upper_bound:
                continue

            if strike in seen_strikes:
                continue

            annotation = ""
            is_atm = False

            # Check if ATM
            if strike == atm_strike:
                annotation = "ATM"
                is_atm = True
            # Check if near range high (within 2%)
            elif range_high and abs(strike - range_high) / range_high < 0.02:
                annotation = "Range High"
            # Check if near range low (within 2%)
            elif range_low and abs(strike - range_low) / range_low < 0.02:
                annotation = "Range Low"
            # Check if near analyst target (within 2%)
            elif target_price and abs(strike - target_price) / target_price < 0.02:
                annotation = "Target"
            # Check if round number
            elif strike % round_interval == 0:
                annotation = "Round"
            else:
                # Skip non-interesting strikes
                continue

            seen_strikes.add(strike)
            interesting.append(
                {
                    "strike": strike,
                    "annotation": annotation,
                    "is_atm": is_atm,
                }
            )

        # Always include ATM even if already captured
        if atm_strike not in seen_strikes:
            interesting.append(
                {
                    "strike": atm_strike,
                    "annotation": "ATM",
                    "is_atm": True,
                }
            )

        # Sort by strike and limit to ~8 strikes
        interesting.sort(key=lambda x: x["strike"])
        return interesting[:8]

    def _format_options_rows(
        self,
        df,
        interesting_strikes: list[float],
        strike_info: dict,
        option_type: str,
    ) -> list[dict]:
        """Format options DataFrame rows for display."""
        rows = []

        if df is None or df.empty:
            return rows

        filtered = df[df["strike"].isin(interesting_strikes)]

        for _, row in filtered.iterrows():
            strike = row["strike"]
            info = strike_info.get(strike, {})
            iv_raw = float(row.get("impliedVolatility", 0) or 0)

            rows.append(
                {
                    "strike": float(strike),
                    "bid": float(row.get("bid", 0) or 0),
                    "ask": float(row.get("ask", 0) or 0),
                    "oi": int(row.get("openInterest", 0) or 0),
                    "iv": iv_raw,
                    "iv_pct": f"{iv_raw * 100:.0f}%",  # Pre-formatted for display
                    "annotation": info.get("annotation", ""),
                    "is_atm": info.get("is_atm", False),
                }
            )

        # Sort calls descending (high strikes first), puts ascending
        if option_type == "call":
            rows.sort(key=lambda x: x["strike"], reverse=True)
        else:
            rows.sort(key=lambda x: x["strike"])

        return rows

    def _build_structured_options_summary(self):
        """Build structured options summary for LLM context."""
        if not self.options_calls and not self.options_puts:
            self.options_summary = "No options data available."
            return

        lines = [
            f"Options for {self.selected_expiration} ({self.options_days_to_expiry} days):",
            "",
            "Calls (sell if owning, buy if bullish):",
        ]

        for c in self.options_calls[:4]:
            ann = f" ({c['annotation']})" if c["annotation"] else ""
            lines.append(
                f"  ${c['strike']:.0f}{ann}: ${c['bid']:.2f} bid, IV {c['iv'] * 100:.0f}%"
            )

        lines.append("")
        lines.append("Puts (sell if bullish, buy if bearish):")

        for p in self.options_puts[:4]:
            ann = f" ({p['annotation']})" if p["annotation"] else ""
            lines.append(
                f"  ${p['strike']:.0f}{ann}: ${p['bid']:.2f} bid, IV {p['iv'] * 100:.0f}%"
            )

        if self.options_atm_iv:
            lines.append("")
            lines.append(f"ATM IV: {self.options_atm_iv * 100:.0f}%")

        self.options_summary = "\n".join(lines)

    def _reset_options(self) -> None:
        """Reset all options-owned state."""
        self.options_expirations = []
        self.selected_expiration = ""
        self.options_calls = []
        self.options_puts = []
        self.options_atm_iv = 0.0
        self.options_days_to_expiry = 0
        self.options_loading = False
        self.options_error = ""
        self.options_summary = ""

