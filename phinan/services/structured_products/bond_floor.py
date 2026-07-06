"""Closed-form bond floor for structured notes.

The bond floor is the present value of the GUARANTEED cashflows only:
protected principal at maturity plus fixed (unconditional) coupons. It is
both a display metric and a sanity anchor for the Monte Carlo engine - a
zero-volatility simulation of a fully protected fixed-coupon note must
reproduce it exactly.

Uses math.erf for the normal CDF so the package has no scipy dependency.
"""

import logging
import math
from datetime import date
from typing import Optional

from ...models.structured_note import StructuredNote
from .payoff import build_note_params, build_observation_schedule

logger = logging.getLogger(__name__)


def norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def closed_form_bond_floor(
    note: StructuredNote, discount_rate: float, as_of: Optional[date] = None
) -> float:
    """PV of the guaranteed component: protected principal + fixed coupons.

    Uses the same observation schedule as the Monte Carlo engine so the
    two agree exactly in the deterministic limit.
    """
    schedule = build_observation_schedule(note, as_of)
    params = build_note_params(note, discount_rate)
    t_maturity = schedule[-1].t_years

    floor = params.capital_protection * math.exp(-discount_rate * t_maturity)

    if params.coupon_type == "Fixed" and params.coupon_per_period > 0:
        for event in schedule:
            floor += params.coupon_per_period * math.exp(
                -discount_rate * event.t_years
            )

    return floor
