"""Single-leg option analytics: Black-Scholes price, Greeks, PoP, payoff.

Pure math, no Reflex, no numpy: everything here is small closed-form
arithmetic suitable for per-keystroke preview recomputation. All prices
and premiums are per share; the 100x contract multiplier is applied only
in dollar-denominated payoff/max-profit functions.

Probability of profit is the risk-neutral lognormal estimate (drift r,
the entered IV) of finishing beyond break-even at expiration - label it
"est. PoP" in any UI.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .structured_products.bond_floor import norm_cdf

logger = logging.getLogger(__name__)

CONTRACT_MULTIPLIER = 100

DAYS_PER_YEAR = 365.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(
    spot: float, strike: float, sigma: float, r: float, t_years: float
) -> Tuple[float, float]:
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    return d1, d1 - sigma * math.sqrt(t_years)


@dataclass(frozen=True)
class Greeks:
    """Per-share option Greeks (theta per calendar day, vega per 1 vol pt)."""

    delta: float
    gamma: float
    theta: float
    vega: float


def intrinsic_value(price: float, strike: float, option_type: str) -> float:
    """Intrinsic value per share at a given underlying price."""
    if option_type == "call":
        return max(price - strike, 0.0)
    return max(strike - price, 0.0)


def bs_price(
    spot: float,
    strike: float,
    sigma: float,
    r: float,
    t_years: float,
    option_type: str,
) -> float:
    """Black-Scholes European option price per share.

    Falls back to intrinsic value when t <= 0 or sigma <= 0.
    """
    if t_years <= 0 or sigma <= 0:
        return intrinsic_value(spot, strike, option_type)
    d1, d2 = _d1_d2(spot, strike, sigma, r, t_years)
    if option_type == "call":
        return spot * norm_cdf(d1) - strike * math.exp(-r * t_years) * norm_cdf(d2)
    return strike * math.exp(-r * t_years) * norm_cdf(-d2) - spot * norm_cdf(-d1)


def bs_greeks(
    spot: float,
    strike: float,
    sigma: float,
    r: float,
    t_years: float,
    option_type: str,
) -> Optional[Greeks]:
    """Black-Scholes Greeks per share (None when t/sigma degenerate)."""
    if t_years <= 0 or sigma <= 0:
        return None
    d1, d2 = _d1_d2(spot, strike, sigma, r, t_years)
    pdf_d1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(t_years)

    if option_type == "call":
        delta = norm_cdf(d1)
        theta_annual = -spot * pdf_d1 * sigma / (2 * sqrt_t) - r * strike * math.exp(
            -r * t_years
        ) * norm_cdf(d2)
    else:
        delta = norm_cdf(d1) - 1.0
        theta_annual = -spot * pdf_d1 * sigma / (2 * sqrt_t) + r * strike * math.exp(
            -r * t_years
        ) * norm_cdf(-d2)

    return Greeks(
        delta=delta,
        gamma=pdf_d1 / (spot * sigma * sqrt_t),
        theta=theta_annual / DAYS_PER_YEAR,
        vega=spot * pdf_d1 * sqrt_t / 100.0,
    )


def break_even(strike: float, premium: float, option_type: str) -> float:
    """Break-even underlying price at expiration (same for long/short)."""
    if option_type == "call":
        return strike + premium
    return strike - premium


def payoff_at_price(
    price: float,
    strike: float,
    premium: float,
    option_type: str,
    position_type: str,
    contracts: int,
) -> float:
    """Dollar P/L at expiration for a given underlying price."""
    intrinsic = intrinsic_value(price, strike, option_type)
    per_share = intrinsic - premium if position_type == "long" else premium - intrinsic
    return per_share * CONTRACT_MULTIPLIER * contracts


def payoff_curve(
    spot: float,
    strike: float,
    premium: float,
    option_type: str,
    position_type: str,
    contracts: int,
    pct_range: float = 0.30,
    n_points: int = 61,
) -> List[dict]:
    """Payoff diagram points over [spot*(1-pct), spot*(1+pct)].

    The grid always includes the strike and break-even prices exactly so
    the chart shows the kink and the zero crossing faithfully.
    """
    lo = max(spot * (1.0 - pct_range), 0.01)
    hi = spot * (1.0 + pct_range)
    step = (hi - lo) / max(n_points - 1, 1)
    prices = {round(lo + i * step, 2) for i in range(n_points)}

    for anchor in (strike, break_even(strike, premium, option_type)):
        if lo <= anchor <= hi:
            prices.add(round(anchor, 2))

    return [
        {
            "price": price,
            "pnl": round(
                payoff_at_price(
                    price, strike, premium, option_type, position_type, contracts
                ),
                2,
            ),
        }
        for price in sorted(prices)
    ]


def max_profit_loss(
    strike: float,
    premium: float,
    option_type: str,
    position_type: str,
    contracts: int,
) -> Tuple[Optional[float], Optional[float]]:
    """(max_profit, max_loss) in dollars; None means unlimited.

    Max loss is reported as a positive magnitude.
    """
    scale = CONTRACT_MULTIPLIER * contracts
    premium_total = premium * scale
    strike_minus_prem = (strike - premium) * scale

    if position_type == "long":
        if option_type == "call":
            return None, premium_total
        return strike_minus_prem, premium_total  # put: max profit at S=0
    # short
    if option_type == "call":
        return premium_total, None
    return premium_total, strike_minus_prem  # put: max loss at S=0


def probability_of_profit(
    spot: float,
    strike: float,
    premium: float,
    sigma: float,
    r: float,
    t_years: float,
    option_type: str,
    position_type: str,
) -> Optional[float]:
    """Risk-neutral lognormal probability of finishing past break-even.

    S_T ~ LN(ln(spot) + (r - sigma^2/2) t, sigma^2 t). Long calls and
    short puts profit above break-even; long puts and short calls below.
    Returns None when sigma <= 0 or t <= 0 (UI shows "N/A").
    """
    if sigma <= 0 or t_years <= 0 or spot <= 0:
        return None
    be = break_even(strike, premium, option_type)
    if be <= 0:
        # Break-even at/below zero: always above it
        p_above = 1.0
    else:
        z = (math.log(spot / be) + (r - 0.5 * sigma**2) * t_years) / (
            sigma * math.sqrt(t_years)
        )
        p_above = norm_cdf(z)

    profits_above = (option_type == "call") == (position_type == "long")
    return p_above if profits_above else 1.0 - p_above


def strategy_label(option_type: str, position_type: str) -> str:
    """Default strategy tag for a type/position combination.

    Short calls default to covered_call and short puts to
    cash_secured_put (how this family trades them); the form lets the
    user override.
    """
    if position_type == "long":
        return "long_call" if option_type == "call" else "long_put"
    return "covered_call" if option_type == "call" else "cash_secured_put"


def preview_strategy(
    spot: float,
    strike: float,
    premium: float,
    option_type: str,
    position_type: str,
    contracts: int,
    sigma: float,
    r: float,
    t_years: float,
) -> dict:
    """One JSON-safe bundle for the strategy preview card.

    Greeks are position-signed (a short position flips the sign) and per
    share.
    """
    max_profit, max_loss = max_profit_loss(
        strike, premium, option_type, position_type, contracts
    )
    greeks = bs_greeks(spot, strike, sigma, r, t_years, option_type)
    sign = 1.0 if position_type == "long" else -1.0

    entry_total = premium * CONTRACT_MULTIPLIER * contracts
    pop = probability_of_profit(
        spot, strike, premium, sigma, r, t_years, option_type, position_type
    )

    return {
        "entry_amount": round(entry_total, 2),
        "is_debit": position_type == "long",
        "break_even": round(break_even(strike, premium, option_type), 2),
        "max_profit": round(max_profit, 2) if max_profit is not None else None,
        "max_loss": round(max_loss, 2) if max_loss is not None else None,
        "unlimited_profit": max_profit is None,
        "unlimited_loss": max_loss is None,
        "pop": round(pop, 4) if pop is not None else None,
        "greeks": (
            {
                "delta": round(sign * greeks.delta, 4),
                "gamma": round(sign * greeks.gamma, 4),
                "theta": round(sign * greeks.theta, 4),
                "vega": round(sign * greeks.vega, 4),
            }
            if greeks
            else None
        ),
        "payoff": payoff_curve(
            spot, strike, premium, option_type, position_type, contracts
        ),
    }
