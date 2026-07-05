"""Structured product analysis service.

Facade over the Monte Carlo engine: fetches market inputs for a note's
underlyings, runs the simulation, and (in later phases) the alternatives
comparison. This is also the surface the future assistant tools will call
(analyze_note / build_market_inputs).
"""

import logging
from datetime import date
from typing import Optional

from ...config.settings import settings
from ...models.structured_note import (
    NoteAnalysis,
    NoteValuation,
    StructuredNote,
)
from .engine import MarketInputs, simulate_note

logger = logging.getLogger(__name__)

# Fallback annualized vol when price history is unavailable for a ticker
FALLBACK_VOL = 0.25

# Tolerance for the deterministic sanity check (30 bps)
BOND_FLOOR_TOLERANCE = 0.003


class StructuredProductService:
    """Service for pricing and analyzing structured products."""

    def __init__(self):
        self._market_data = None

    def _get_market_data(self):
        if self._market_data is None:
            from .. import services

            self._market_data = services.market_data
        return self._market_data

    def build_market_inputs(
        self,
        note: StructuredNote,
        rf_override: Optional[float] = None,
        spread_override: Optional[float] = None,
        correlation_override: Optional[float] = None,
    ) -> MarketInputs:
        """Fetch spot prices and realized vols for the note's underlyings.

        Spot failures are fatal (raises ValueError naming the tickers so
        the user can correct the form). A missing price history falls back
        to FALLBACK_VOL with a warning; the value used is surfaced in the
        result's audit trail either way.
        """
        sp = settings.structured_products
        md = self._get_market_data()

        spots: dict[str, float] = {}
        vols: dict[str, float] = {}
        failed: list[str] = []

        for ticker in note.underlying_tickers:
            info = md.get_ticker_info(ticker)
            if info is None or not info.current_price:
                failed.append(ticker)
                continue
            spots[ticker] = float(info.current_price)
            vols[ticker] = self._realized_vol(md, ticker, sp.vol_lookback_period)

        if failed:
            raise ValueError(
                f"Could not fetch market data for: {', '.join(failed)}. "
                "Check the ticker symbols and try again."
            )
        if not spots:
            raise ValueError("Note has no underlying tickers")

        return MarketInputs(
            spots=spots,
            vols=vols,
            risk_free_rate=(
                rf_override if rf_override is not None else sp.risk_free_rate
            ),
            credit_spread=(
                spread_override
                if spread_override is not None
                else sp.default_credit_spread
            ),
            correlation=(
                correlation_override
                if correlation_override is not None
                else sp.default_correlation
            ),
        )

    def _realized_vol(self, md, ticker: str, period: str) -> float:
        """Annualized realized vol from daily log returns, with fallback."""
        import numpy as np

        try:
            history = md.get_price_history(ticker, period=period, interval="1d")
            if history is None or history.empty or len(history) < 30:
                raise ValueError("insufficient price history")
            col_map = {c.lower(): c for c in history.columns}
            close = history[col_map["close"]]
            returns = np.log(close / close.shift(1)).dropna()
            vol = float(returns.std() * np.sqrt(252))
            if not (0.01 <= vol <= 3.0):
                raise ValueError(f"implausible vol {vol:.2f}")
            return vol
        except Exception as e:
            logger.warning(
                "Falling back to %.0f%% vol for %s: %s",
                FALLBACK_VOL * 100,
                ticker,
                e,
            )
            return FALLBACK_VOL

    def analyze_note(
        self,
        note: StructuredNote,
        market: Optional[MarketInputs] = None,
        n_paths: Optional[int] = None,
        seed: Optional[int] = None,
        as_of: Optional[date] = None,
    ) -> NoteAnalysis:
        """Run the full Monte Carlo analysis for a note."""
        if market is None:
            market = self.build_market_inputs(note)

        simulation, _worst_terminal = simulate_note(
            note, market, n_paths=n_paths, seed=seed, as_of=as_of
        )

        self._sanity_check_bond_floor(note, simulation)

        return NoteAnalysis(note=note, simulation=simulation)

    def _sanity_check_bond_floor(self, note: StructuredNote, simulation) -> None:
        """Warn if MC and closed form disagree on a fully guaranteed note."""
        fully_guaranteed = (
            (note.capital_protection or 0.0) >= 100.0
            and note.coupon_type == "Fixed"
            and not note.autocall_barrier
        )
        if not fully_guaranteed:
            return
        diff = abs(simulation.fair_value_pct - simulation.bond_floor_pct)
        if diff > BOND_FLOOR_TOLERANCE:
            logger.warning(
                "MC fair value %.4f deviates from closed-form bond floor "
                "%.4f by %.1f bps on a fully guaranteed note",
                simulation.fair_value_pct,
                simulation.bond_floor_pct,
                diff * 10_000,
            )

    def calculate_fair_value(self, note: StructuredNote) -> NoteValuation:
        """TEMPORARY shim keeping the pre-rewrite notes UI working.

        Maps a Monte Carlo analysis onto the legacy NoteValuation shape.
        Removed in phase 2 together with NoteValuation.
        """
        try:
            market = self.build_market_inputs(note)
        except Exception as e:
            logger.warning(
                "Market data unavailable for shim valuation, using "
                "fallback inputs: %s",
                e,
            )
            sp = settings.structured_products
            market = MarketInputs(
                spots={t: 1.0 for t in note.underlying_tickers},
                vols={t: FALLBACK_VOL for t in note.underlying_tickers},
                risk_free_rate=sp.risk_free_rate,
                credit_spread=sp.default_credit_spread,
                correlation=sp.default_correlation,
            )

        simulation, _ = simulate_note(note, market, n_paths=4_000)
        return NoteValuation(
            fair_value_pct=simulation.fair_value_pct,
            bond_floor_pct=simulation.bond_floor_pct,
            option_value_pct=simulation.option_value_pct,
            implied_fee_pct=simulation.implied_fee_pct,
            break_even_pct=round(1.0 + simulation.percentiles.get("p50", 0.0), 4),
            probability_of_loss=simulation.prob_loss,
            probability_of_autocall=simulation.prob_autocall,
        )
