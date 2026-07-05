"""Monte Carlo simulation engine for structured notes.

Simulates correlated GBM paths for the worst-of basket and aggregates
payoff outcomes into a SimulationResult. Paths are streamed in chunks and
never stored whole: per chunk only the current levels, the worst-of
snapshots at observation dates, and the running minimum are kept.

Determinism: a single numpy Generator seeded once is drawn sequentially
across chunks, so results are bit-reproducible for a fixed
(seed, n_paths, chunk_size).
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ...config.settings import settings
from ...models.structured_note import (
    AutocallProbability,
    OutcomeBucket,
    SimulationResult,
    StructuredNote,
)
from .payoff import (
    MIN_T_YEARS,
    build_note_params,
    build_observation_schedule,
    evaluate_paths,
)

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252

# Annualized return per path is clipped to this horizon so a near-instant
# autocall does not produce an absurd annualization
MIN_IRR_HORIZON_YEARS = 1.0 / 12.0


@dataclass
class MarketInputs:
    """Market data inputs for a simulation (per underlying ticker)."""

    spots: Dict[str, float]
    vols: Dict[str, float]  # annualized realized/forecast vol
    risk_free_rate: float
    credit_spread: float
    correlation: float
    dividend_yields: Dict[str, float] = field(default_factory=dict)


def _correlation_cholesky(n_assets: int, rho: float) -> "np.ndarray":
    """Cholesky factor of an equicorrelation matrix, with fallbacks."""
    import numpy as np

    if n_assets == 1:
        return np.ones((1, 1))

    rho = float(min(max(rho, 0.0), 0.99))
    corr = np.full((n_assets, n_assets), rho)
    np.fill_diagonal(corr, 1.0)
    try:
        return np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        # Jitter the diagonal; equicorrelation with rho in [0, 1) is PD,
        # so this is belt-and-braces for numerical edge cases.
        corr += np.eye(n_assets) * 1e-8
        return np.linalg.cholesky(corr)


def simulate_note(
    note: StructuredNote,
    market: MarketInputs,
    n_paths: Optional[int] = None,
    seed: Optional[int] = None,
    as_of: Optional[date] = None,
    chunk_size: int = 2_500,
) -> Tuple[SimulationResult, "np.ndarray"]:
    """Simulate a structured note and aggregate valuation/risk metrics.

    Args:
        note: parsed/edited note terms. Must have a future maturity date
            and at least one underlying ticker.
        market: spot/vol/rate inputs (see MarketInputs).
        n_paths: number of Monte Carlo paths (default from settings,
            clamped to settings max).
        seed: RNG seed for reproducibility (None = nondeterministic).
        as_of: analysis date (default today). v1 assumes at-issuance
            evaluation: all levels are normalized to 1.0 at as_of.
        chunk_size: paths simulated per streaming chunk.

    Returns:
        (SimulationResult, terminal worst-of levels array) - the terminal
        array is reused by the alternatives comparison.
    """
    import numpy as np

    sp = settings.structured_products
    n_paths = int(min(n_paths or sp.default_n_paths, sp.max_paths))
    as_of = as_of or date.today()

    tickers = list(note.underlying_tickers)
    if not tickers:
        raise ValueError("Note has no underlying tickers")
    missing_vols = [t for t in tickers if t not in market.vols]
    if missing_vols:
        raise ValueError(f"Missing volatility inputs for: {', '.join(missing_vols)}")

    schedule = build_observation_schedule(note, as_of)
    discount_rate = market.risk_free_rate + market.credit_spread
    params = build_note_params(note, discount_rate)

    n_assets = len(tickers)
    vols = np.array([market.vols[t] for t in tickers])
    divs = np.array([market.dividend_yields.get(t, 0.0) for t in tickers])
    r = market.risk_free_rate
    chol = _correlation_cholesky(n_assets, market.correlation)

    t_maturity = schedule[-1].t_years
    obs_times = np.array([e.t_years for e in schedule])
    n_obs = len(schedule)

    # Time grid: daily steps only when the barrier needs continuous
    # monitoring; otherwise step directly between observation dates.
    monitor_daily = params.barrier_type == "American" and params.protection_barrier
    if monitor_daily:
        n_steps = max(int(np.ceil(t_maturity * TRADING_DAYS_PER_YEAR)), n_obs)
        step_times = np.linspace(t_maturity / n_steps, t_maturity, n_steps)
        # Map each observation to the nearest step (final obs -> last step)
        obs_step_idx = np.minimum(
            np.searchsorted(step_times, obs_times - 1e-12), n_steps - 1
        )
        obs_step_idx[-1] = n_steps - 1
    else:
        n_steps = n_obs
        step_times = obs_times
        obs_step_idx = np.arange(n_obs)

    dts = np.diff(np.concatenate([[0.0], step_times]))
    dts = np.maximum(dts, MIN_T_YEARS / 365.0)

    # Precompute per-step drift/diffusion terms (n_steps, n_assets)
    drift = (r - divs - 0.5 * vols**2)[None, :] * dts[:, None]
    diffusion = vols[None, :] * np.sqrt(dts)[:, None]

    rng = np.random.default_rng(seed)
    is_obs_step = np.zeros(n_steps, dtype=bool)
    is_obs_step[obs_step_idx] = True
    step_to_obs = {int(s): i for i, s in enumerate(obs_step_idx)}

    pv_parts = []
    cash_parts = []
    redemption_parts = []
    autocall_parts = []
    breached_parts = []
    worst_T_parts = []

    remaining = n_paths
    while remaining > 0:
        chunk = min(chunk_size, remaining)
        remaining -= chunk

        log_levels = np.zeros((chunk, n_assets))
        worst_at_obs = np.empty((chunk, n_obs))
        running_min = np.ones(chunk)

        for s in range(n_steps):
            z = rng.standard_normal((chunk, n_assets))
            eps = z @ chol.T
            log_levels += drift[s] + diffusion[s] * eps
            worst = np.exp(log_levels.min(axis=1))
            if monitor_daily:
                running_min = np.minimum(running_min, worst)
            if is_obs_step[s]:
                worst_at_obs[:, step_to_obs[s]] = worst
        if not monitor_daily:
            running_min = worst_at_obs.min(axis=1)

        outcomes = evaluate_paths(worst_at_obs, running_min, schedule, params)
        pv_parts.append(outcomes.pv)
        cash_parts.append(outcomes.total_cash)
        redemption_parts.append(outcomes.redemption_t)
        autocall_parts.append(outcomes.autocall_idx)
        breached_parts.append(outcomes.breached)
        worst_T_parts.append(outcomes.worst_at_maturity)

    pv = np.concatenate(pv_parts)
    total_cash = np.concatenate(cash_parts)
    redemption_t = np.concatenate(redemption_parts)
    autocall_idx = np.concatenate(autocall_parts)
    breached = np.concatenate(breached_parts)
    worst_T = np.concatenate(worst_T_parts)

    result = _aggregate(
        note=note,
        market=market,
        schedule=schedule,
        pv=pv,
        total_cash=total_cash,
        redemption_t=redemption_t,
        autocall_idx=autocall_idx,
        breached=breached,
        n_paths=n_paths,
        seed=seed,
        as_of=as_of,
    )
    return result, worst_T


def _aggregate(
    note: StructuredNote,
    market: MarketInputs,
    schedule,
    pv,
    total_cash,
    redemption_t,
    autocall_idx,
    breached,
    n_paths: int,
    seed: Optional[int],
    as_of: date,
) -> SimulationResult:
    """Reduce per-path outcomes to a SimulationResult."""
    import numpy as np

    from .bond_floor import closed_form_bond_floor

    sp = settings.structured_products

    fair_value = float(pv.mean())
    bond_floor = closed_form_bond_floor(
        note, market.risk_free_rate + market.credit_spread, as_of=as_of
    )

    total_return = total_cash - 1.0
    horizon = np.maximum(redemption_t, MIN_IRR_HORIZON_YEARS)
    annualized = np.power(np.maximum(total_cash, 0.0), 1.0 / horizon) - 1.0

    # Autocall probabilities per observation date
    n_obs = len(schedule)
    called = autocall_idx >= 0
    counts = np.bincount(autocall_idx[called], minlength=n_obs)
    cumulative = 0.0
    autocall_by_date = []
    for i, event in enumerate(schedule):
        p = float(counts[i]) / n_paths
        if event.is_final:
            # No autocall decision at maturity
            continue
        if event.autocall_trigger is None:
            continue
        cumulative += p
        autocall_by_date.append(
            AutocallProbability(
                date=event.date,
                t_years=round(event.t_years, 4),
                probability=round(p, 4),
                cumulative=round(cumulative, 4),
            )
        )

    percentile_values = np.percentile(total_return, [5, 25, 50, 75, 95])
    percentiles = {
        key: round(float(v), 4)
        for key, v in zip(["p5", "p25", "p50", "p75", "p95"], percentile_values)
    }

    histogram = _build_histogram(total_return, sp.histogram_buckets)

    return SimulationResult(
        fair_value_pct=round(fair_value, 4),
        bond_floor_pct=round(bond_floor, 4),
        option_value_pct=round(fair_value - bond_floor, 4),
        implied_fee_pct=round(1.0 - fair_value, 4),
        expected_return_pct=round(float(total_return.mean()), 4),
        expected_irr=round(float(annualized.mean()), 4),
        median_irr=round(float(np.median(annualized)), 4),
        prob_autocall=round(float(called.mean()), 4),
        prob_barrier_breach=round(float(breached.mean()), 4),
        prob_loss=round(float((total_cash < 1.0 - 1e-12).mean()), 4),
        expected_life_years=round(float(redemption_t.mean()), 4),
        percentiles=percentiles,
        autocall_by_date=autocall_by_date,
        histogram=histogram,
        n_paths=n_paths,
        seed=seed,
        risk_free_rate=market.risk_free_rate,
        credit_spread=market.credit_spread,
        correlation_used=market.correlation,
        vols_used={t: round(v, 4) for t, v in market.vols.items()},
        spots_used={t: round(v, 4) for t, v in market.spots.items()},
    )


def _build_histogram(total_return, n_buckets: int) -> list:
    """Downsample the outcome distribution to a small bucketed histogram."""
    import numpy as np

    lo = float(np.percentile(total_return, 1))
    hi = float(np.percentile(total_return, 99))
    if hi - lo < 1e-9:
        # Degenerate distribution (e.g. vol=0): a single bucket
        return [
            OutcomeBucket(
                label=f"{lo * 100:+.1f}%",
                low=round(lo, 4),
                high=round(hi, 4),
                pct=100.0,
            )
        ]

    edges = np.linspace(lo, hi, n_buckets + 1)
    clipped = np.clip(total_return, lo, hi)
    counts, _ = np.histogram(clipped, bins=edges)
    buckets = []
    for i in range(n_buckets):
        low, high = float(edges[i]), float(edges[i + 1])
        buckets.append(
            OutcomeBucket(
                label=f"{low * 100:+.0f}%",
                low=round(low, 4),
                high=round(high, 4),
                pct=round(float(counts[i]) / len(total_return) * 100.0, 2),
            )
        )
    return buckets
