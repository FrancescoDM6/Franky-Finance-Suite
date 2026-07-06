"""Alternative strategy comparison for structured notes.

Answers "what else could this money do over the same horizon?" by
restating the note next to simple alternatives evaluated on the SAME
simulated terminal distribution where possible. Every approximated row
carries an honest caveat rendered in the UI.
"""

import logging
import math
from typing import TYPE_CHECKING, List

from ...models.structured_note import (
    AlternativeResult,
    SimulationResult,
    StructuredNote,
)
from .bond_floor import norm_cdf
from .engine import MarketInputs

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

# Covered-call stylization: strike moneyness of the monthly call sold.
# TUNE(Franky): 1.02 = 2% OTM; raise for more upside/less income.
COVERED_CALL_MONEYNESS = 1.02
COVERED_CALL_TENOR_YEARS = 1.0 / 12.0

MIN_HORIZON_YEARS = 1.0 / 12.0


def bs_call(s: float, k: float, sigma: float, r: float, t: float) -> float:
    """Black-Scholes European call price."""
    if t <= 0 or sigma <= 0:
        return max(s - k, 0.0)
    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return s * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2)


def bs_put(s: float, k: float, sigma: float, r: float, t: float) -> float:
    """Black-Scholes European put price."""
    if t <= 0 or sigma <= 0:
        return max(k - s, 0.0)
    d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return k * math.exp(-r * t) * norm_cdf(-d2) - s * norm_cdf(-d1)


def _annualize(total_return, t_years: float):
    """Annualized simple return from a total return over t_years."""
    import numpy as np

    t = max(t_years, MIN_HORIZON_YEARS)
    growth = np.maximum(1.0 + total_return, 0.0)
    return np.power(growth, 1.0 / t) - 1.0


def _stats_row(
    strategy: str, total_return, t_years: float, caveat: str
) -> AlternativeResult:
    """Build a comparison row from a per-path total-return array."""
    import numpy as np

    total_return = np.asarray(total_return, dtype=float)
    annualized = _annualize(total_return, t_years)
    p5, p50, p95 = np.percentile(total_return, [5, 50, 95])
    return AlternativeResult(
        strategy=strategy,
        expected_return_pct=round(float(total_return.mean()), 4),
        expected_irr=round(float(annualized.mean()), 4),
        max_loss_pct=round(float(total_return.min()), 4),
        p5=round(float(p5), 4),
        p50=round(float(p50), 4),
        p95=round(float(p95), 4),
        caveat=caveat,
    )


def compare_alternatives(
    note: StructuredNote,
    market: MarketInputs,
    simulation: SimulationResult,
    worst_terminal: "np.ndarray",
    t_years: float,
) -> List[AlternativeResult]:
    """Compare the note against simple alternative strategies.

    Rows: the note itself (restated from the simulation), direct equity
    in the same worst-of exposure, a stylized covered-call strategy, and
    a risk-free bond. Equity-based rows reuse the note's simulated
    terminal distribution so the comparison is apples-to-apples.
    """
    import numpy as np

    t = max(t_years, MIN_HORIZON_YEARS)
    r = market.risk_free_rate
    rows: List[AlternativeResult] = []

    # 1. The note, restated from the simulation
    p = simulation.percentiles
    rows.append(
        AlternativeResult(
            strategy="This note",
            expected_return_pct=simulation.expected_return_pct,
            expected_irr=simulation.expected_irr,
            max_loss_pct=round((note.capital_protection or 0.0) / 100.0 - 1.0, 4),
            p5=p.get("p5", 0.0),
            p50=p.get("p50", 0.0),
            p95=p.get("p95", 0.0),
            caveat="Held to redemption; issuer credit risk not shown",
        )
    )

    # 2. Direct equity in the same worst-of exposure
    equity_return = np.asarray(worst_terminal, dtype=float) - 1.0
    rows.append(
        _stats_row(
            "Direct equity (worst-of)",
            equity_return,
            t,
            "Buy-and-hold of the same worst-of exposure; dividends ignored",
        )
    )

    # 3. Stylized covered-call strategy on the same exposure
    sigma = float(np.mean(list(market.vols.values()))) if market.vols else 0.25
    monthly_premium = bs_call(
        1.0, COVERED_CALL_MONEYNESS, sigma, r, COVERED_CALL_TENOR_YEARS
    )
    n_months = max(int(round(t * 12)), 1)
    premium_income = monthly_premium * n_months
    upside_cap = COVERED_CALL_MONEYNESS ** n_months
    covered_call_return = (
        np.minimum(np.asarray(worst_terminal, dtype=float), upside_cap)
        - 1.0
        + premium_income
    )
    rows.append(
        _stats_row(
            "Covered calls (monthly)",
            covered_call_return,
            t,
            f"Stylized: sell 1-month {int((COVERED_CALL_MONEYNESS - 1) * 100)}% OTM "
            "calls; premium held as cash, path dependency ignored",
        )
    )

    # 4. Risk-free bond (deterministic)
    rf_total = math.exp(r * t) - 1.0
    rows.append(
        AlternativeResult(
            strategy="Risk-free bond",
            expected_return_pct=round(rf_total, 4),
            expected_irr=round(math.exp(r) - 1.0, 4),
            max_loss_pct=0.0,
            p5=round(rf_total, 4),
            p50=round(rf_total, 4),
            p95=round(rf_total, 4),
            caveat="US Treasury proxy at the configured risk-free rate",
        )
    )

    return rows
