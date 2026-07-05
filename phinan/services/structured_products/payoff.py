"""Pure payoff evaluation for structured notes.

This module is deterministic and market-data-free: it turns a matrix of
simulated worst-of levels at observation dates into per-path cashflows.
Unit tests feed synthetic matrices and assert exact results.

Conventions: all levels are fractions of the initial fixing (1.0 = 100%),
all times are year fractions from the analysis date, all cash amounts are
fractions of notional.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, List, Optional

from ...models.structured_note import StructuredNote

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

PERIODS_PER_YEAR = {
    "Monthly": 12,
    "Quarterly": 4,
    "Semi-Annual": 2,
    "Annual": 1,
}

# Floor on any year fraction to avoid divide-by-zero on same-day events
MIN_T_YEARS = 1.0 / 365.0


@dataclass
class ObservationEvent:
    """A single observation of the note's life."""

    t_years: float
    date: Optional[date] = None
    autocall_trigger: Optional[float] = None  # fraction of initial; None = no autocall here
    coupon_trigger: Optional[float] = None  # fraction; None = coupon unconditional
    is_final: bool = False


@dataclass
class NoteParams:
    """Payoff parameters derived from a StructuredNote."""

    coupon_per_period: float  # fraction of notional paid per observation
    coupon_type: str  # Fixed | Contingent | Memory
    protection_barrier: Optional[float]  # fraction; None = no conditional barrier
    capital_protection: float  # fraction of notional guaranteed at maturity
    strike: float  # fraction; downside participation reference
    barrier_type: str  # European | American
    discount_rate: float  # risk_free + credit_spread, for PV


@dataclass
class PathOutcomes:
    """Per-path results of evaluate_paths (numpy arrays, length n_paths)."""

    pv: "np.ndarray"  # discounted value of all cashflows
    total_cash: "np.ndarray"  # undiscounted cash received per 1.0 invested
    redemption_t: "np.ndarray"  # year fraction when the path redeemed
    autocall_idx: "np.ndarray"  # observation index of autocall, -1 if none
    breached: "np.ndarray"  # bool, protection barrier breached at redemption
    worst_at_maturity: "np.ndarray" = field(default=None)  # terminal worst-of level


def build_observation_schedule(
    note: StructuredNote, as_of: Optional[date] = None
) -> List[ObservationEvent]:
    """Build the observation schedule for a note.

    Uses the note's explicit observation_dates when present (past dates
    skipped); otherwise synthesizes a regular schedule from the coupon
    frequency. A final event at maturity is always present.

    Raises:
        ValueError: if the maturity date is missing or in the past.
    """
    as_of = as_of or date.today()

    if not note.maturity_date:
        raise ValueError("Note has no maturity date; cannot build schedule")
    if note.maturity_date <= as_of:
        raise ValueError(
            f"Maturity date {note.maturity_date} is not after analysis date {as_of}"
        )

    t_maturity = max((note.maturity_date - as_of).days / 365.0, MIN_T_YEARS)

    default_autocall = (
        note.autocall_barrier / 100.0 if note.autocall_barrier else None
    )
    if note.coupon_type == "Fixed":
        default_coupon_trigger = None
    else:
        default_coupon_trigger = (
            note.coupon_barrier / 100.0 if note.coupon_barrier else None
        )

    events: List[ObservationEvent] = []

    explicit = [o for o in note.observation_dates if as_of < o.date <= note.maturity_date]
    if explicit:
        explicit.sort(key=lambda o: o.date)
        for obs in explicit:
            t = max((obs.date - as_of).days / 365.0, MIN_T_YEARS)
            autocall = (
                obs.autocall_trigger / 100.0
                if obs.autocall_trigger
                else default_autocall
            )
            coupon = (
                obs.coupon_trigger / 100.0
                if obs.coupon_trigger
                else default_coupon_trigger
            )
            events.append(
                ObservationEvent(
                    t_years=t,
                    date=obs.date,
                    autocall_trigger=autocall,
                    coupon_trigger=coupon,
                )
            )
        # Force a final event at maturity
        if events[-1].date != note.maturity_date:
            events.append(
                ObservationEvent(
                    t_years=t_maturity,
                    date=note.maturity_date,
                    autocall_trigger=None,
                    coupon_trigger=default_coupon_trigger,
                )
            )
    else:
        ppy = PERIODS_PER_YEAR.get(note.coupon_frequency, 4)
        n_obs = max(int(round(t_maturity * ppy)), 1)
        for i in range(1, n_obs + 1):
            t = min(i / ppy, t_maturity)
            events.append(
                ObservationEvent(
                    t_years=t,
                    date=as_of + timedelta(days=int(round(t * 365.0))),
                    autocall_trigger=default_autocall,
                    coupon_trigger=default_coupon_trigger,
                )
            )
        events[-1].t_years = t_maturity
        events[-1].date = note.maturity_date

    events[-1].is_final = True
    # No autocall decision on the final observation - maturity redemption
    # logic handles it.
    events[-1].autocall_trigger = None
    return events


def build_note_params(
    note: StructuredNote, discount_rate: float
) -> NoteParams:
    """Derive payoff parameters from a note's terms."""
    ppy = PERIODS_PER_YEAR.get(note.coupon_frequency, 4)
    coupon_per_period = (note.coupon_rate_pa or 0.0) / 100.0 / ppy

    return NoteParams(
        coupon_per_period=coupon_per_period,
        coupon_type=note.coupon_type,
        protection_barrier=(
            note.protection_barrier / 100.0 if note.protection_barrier else None
        ),
        capital_protection=(note.capital_protection or 0.0) / 100.0,
        strike=(note.strike_price or 100.0) / 100.0,
        barrier_type=note.barrier_type,
        discount_rate=discount_rate,
    )


def evaluate_paths(
    worst_at_obs: "np.ndarray",
    running_min: "np.ndarray",
    schedule: List[ObservationEvent],
    params: NoteParams,
) -> PathOutcomes:
    """Evaluate the note payoff over simulated paths.

    Args:
        worst_at_obs: (n_paths, n_obs) worst-of basket level at each
            observation date.
        running_min: (n_paths,) minimum worst-of level over the note's
            life (daily monitoring; used for American barriers).
        schedule: observation events from build_observation_schedule.
        params: payoff parameters from build_note_params.

    Returns:
        PathOutcomes with per-path pv, cash, redemption time, autocall
        index, and breach flags.

    Event loop per observation: pay the coupon (Fixed always; Contingent
    if worst >= trigger; Memory pays 1 + missed catch-up), then autocall
    (redeem 100%, path dies). Surviving paths redeem at maturity: 100% if
    the barrier held, else max(capital_protection, worst/strike capped at
    100%) - physical delivery of the worst performer, protection-floored.
    """
    import numpy as np

    n_paths, n_obs = worst_at_obs.shape
    if n_obs != len(schedule):
        raise ValueError(
            f"worst_at_obs has {n_obs} observations but schedule has {len(schedule)}"
        )

    alive = np.ones(n_paths, dtype=bool)
    pv = np.zeros(n_paths)
    total_cash = np.zeros(n_paths)
    missed = np.zeros(n_paths)  # missed coupon count for Memory notes
    redemption_t = np.full(n_paths, schedule[-1].t_years)
    autocall_idx = np.full(n_paths, -1, dtype=np.int64)

    for i, event in enumerate(schedule):
        if not alive.any():
            break
        worst = worst_at_obs[:, i]
        df = float(np.exp(-params.discount_rate * event.t_years))

        # 1. Coupon
        if params.coupon_per_period > 0:
            if params.coupon_type == "Fixed" or event.coupon_trigger is None:
                paid = alive
                units = np.ones(n_paths)
            else:
                eligible = alive & (worst >= event.coupon_trigger)
                if params.coupon_type == "Memory":
                    units = 1.0 + missed
                    missed = np.where(eligible, 0.0, missed)
                    missed = np.where(alive & ~eligible, missed + 1.0, missed)
                else:  # Contingent
                    units = np.ones(n_paths)
                paid = eligible
            cash = params.coupon_per_period * units
            total_cash[paid] += cash[paid]
            pv[paid] += cash[paid] * df

        # 2. Autocall (never on the final observation)
        if event.autocall_trigger is not None and not event.is_final:
            called = alive & (worst >= event.autocall_trigger)
            if called.any():
                total_cash[called] += 1.0
                pv[called] += 1.0 * df
                redemption_t[called] = event.t_years
                autocall_idx[called] = i
                alive &= ~called

    # 3. Maturity redemption for surviving paths
    final = schedule[-1]
    worst_T = worst_at_obs[:, -1]
    df_T = float(np.exp(-params.discount_rate * final.t_years))

    breached = np.zeros(n_paths, dtype=bool)
    if params.capital_protection < 1.0 and params.protection_barrier is not None:
        if params.barrier_type == "American":
            breached = running_min < params.protection_barrier
        else:
            breached = worst_T < params.protection_barrier
    breached &= alive

    downside = np.maximum(
        params.capital_protection,
        np.minimum(worst_T / params.strike, 1.0),
    )
    redemption = np.where(breached, downside, 1.0)
    total_cash[alive] += redemption[alive]
    pv[alive] += redemption[alive] * df_T

    return PathOutcomes(
        pv=pv,
        total_cash=total_cash,
        redemption_t=redemption_t,
        autocall_idx=autocall_idx,
        breached=breached,
        worst_at_maturity=worst_T,
    )
