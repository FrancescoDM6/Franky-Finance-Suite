"""Unit tests for the structured note payoff core (pure, deterministic)."""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from phinan.models.structured_note import ObservationDate, StructuredNote
from phinan.services.structured_products.payoff import (
    build_note_params,
    build_observation_schedule,
    evaluate_paths,
)

TODAY = date(2026, 7, 1)


def make_note(**overrides) -> StructuredNote:
    defaults = dict(
        issuer="Test Bank",
        product_name="Test Autocallable",
        underlying_tickers=["AAA"],
        maturity_date=TODAY + timedelta(days=365),
        coupon_rate_pa=8.0,
        coupon_frequency="Quarterly",
        coupon_type="Contingent",
        coupon_barrier=70.0,
        autocall_barrier=None,
        protection_barrier=60.0,
        barrier_type="European",
        capital_protection=0.0,
        strike_price=100.0,
    )
    defaults.update(overrides)
    return StructuredNote(**defaults)


@pytest.mark.unit
class TestObservationSchedule:
    def test_synthesizes_quarterly_schedule(self):
        note = make_note()
        schedule = build_observation_schedule(note, as_of=TODAY)

        assert len(schedule) == 4
        assert schedule[-1].is_final is True
        assert schedule[-1].autocall_trigger is None
        assert schedule[-1].t_years == pytest.approx(1.0, abs=0.01)
        assert schedule[0].t_years == pytest.approx(0.25, abs=0.01)

    def test_uses_explicit_observation_dates_and_skips_past(self):
        note = make_note(
            autocall_barrier=100.0,
            observation_dates=[
                ObservationDate(date=TODAY - timedelta(days=30)),  # past: skipped
                ObservationDate(date=TODAY + timedelta(days=180), autocall_trigger=95.0),
            ],
        )
        schedule = build_observation_schedule(note, as_of=TODAY)

        # explicit obs + forced final at maturity
        assert len(schedule) == 2
        assert schedule[0].autocall_trigger == pytest.approx(0.95)
        assert schedule[1].is_final is True
        assert schedule[1].date == note.maturity_date

    def test_fixed_coupon_has_no_trigger(self):
        note = make_note(coupon_type="Fixed")
        schedule = build_observation_schedule(note, as_of=TODAY)
        assert all(e.coupon_trigger is None for e in schedule)

    def test_missing_maturity_raises(self):
        note = make_note(maturity_date=None)
        with pytest.raises(ValueError, match="maturity"):
            build_observation_schedule(note, as_of=TODAY)

    def test_past_maturity_raises(self):
        note = make_note(maturity_date=TODAY - timedelta(days=1))
        with pytest.raises(ValueError, match="not after"):
            build_observation_schedule(note, as_of=TODAY)


def evaluate(note, worst_at_obs, running_min=None, discount_rate=0.0):
    """Helper: schedule + params + evaluate for a synthetic matrix."""
    schedule = build_observation_schedule(note, as_of=TODAY)
    params = build_note_params(note, discount_rate)
    worst = np.asarray(worst_at_obs, dtype=float)
    if running_min is None:
        running_min = worst.min(axis=1)
    return evaluate_paths(worst, np.asarray(running_min, dtype=float), schedule, params)


@pytest.mark.unit
class TestCoupons:
    def test_fixed_coupons_always_pay(self):
        note = make_note(coupon_type="Fixed")
        # 4 quarterly obs, worst stays at par; coupon = 8%/4 = 2% per obs
        out = evaluate(note, [[1.0, 1.0, 1.0, 1.0]])
        assert out.total_cash[0] == pytest.approx(4 * 0.02 + 1.0)

    def test_contingent_coupons_skip_below_barrier(self):
        note = make_note(coupon_type="Contingent", coupon_barrier=70.0)
        # Below the 70% coupon barrier at obs 1 and 2
        out = evaluate(note, [[0.65, 0.65, 0.80, 0.80]])
        assert out.total_cash[0] == pytest.approx(2 * 0.02 + 1.0)

    def test_memory_coupon_catches_up(self):
        note = make_note(coupon_type="Memory", coupon_barrier=70.0)
        # Missed at obs 1 and 2; obs 3 pays 3 units (1 + 2 missed); obs 4 pays 1
        out = evaluate(note, [[0.65, 0.65, 0.80, 0.80]])
        assert out.total_cash[0] == pytest.approx(4 * 0.02 + 1.0)

    def test_memory_missed_coupons_lost_if_never_recovered(self):
        note = make_note(coupon_type="Memory", coupon_barrier=70.0)
        out = evaluate(note, [[0.65, 0.65, 0.65, 0.80]])
        # Only the final observation pays: 1 + 3 missed = 4 units
        assert out.total_cash[0] == pytest.approx(4 * 0.02 + 1.0)

    def test_memory_never_recovered_pays_nothing(self):
        note = make_note(coupon_type="Memory", coupon_barrier=70.0)
        out = evaluate(note, [[0.65, 0.65, 0.65, 0.65]])
        # Never above barrier: no coupons; final worst 0.65 > 0.60 barrier holds
        assert out.total_cash[0] == pytest.approx(1.0)


@pytest.mark.unit
class TestAutocall:
    def test_autocall_short_circuits_path(self):
        note = make_note(autocall_barrier=100.0)
        out = evaluate(note, [[1.05, 1.10, 1.10, 1.10]])

        # Called at first obs: coupon (1.05 >= 0.70) + principal, nothing after
        assert out.total_cash[0] == pytest.approx(0.02 + 1.0)
        assert out.autocall_idx[0] == 0
        assert out.redemption_t[0] == pytest.approx(0.25, abs=0.01)
        assert not out.breached[0]

    def test_no_autocall_below_trigger(self):
        note = make_note(autocall_barrier=100.0)
        out = evaluate(note, [[0.99, 0.99, 0.99, 0.99]])
        assert out.autocall_idx[0] == -1
        # All coupons paid (0.99 >= 0.70), full principal (0.99 >= 0.60)
        assert out.total_cash[0] == pytest.approx(4 * 0.02 + 1.0)

    def test_final_observation_never_autocalls(self):
        note = make_note(autocall_barrier=100.0)
        out = evaluate(note, [[0.9, 0.9, 0.9, 1.20]])
        assert out.autocall_idx[0] == -1
        assert out.redemption_t[0] == pytest.approx(1.0, abs=0.01)


@pytest.mark.unit
class TestBarrierAndRedemption:
    def test_european_vs_american_divergence(self):
        # Intra-life dip below the 60% barrier, but recovery by maturity
        worst_at_obs = [[0.80, 0.75, 0.70, 0.85]]
        running_min = [0.55]

        euro = make_note(barrier_type="European")
        amer = make_note(barrier_type="American")

        out_e = evaluate(euro, worst_at_obs, running_min)
        out_a = evaluate(amer, worst_at_obs, running_min)

        assert not out_e.breached[0]
        assert out_a.breached[0]
        # European redeems par; American delivers the worst performer
        assert out_e.total_cash[0] == pytest.approx(4 * 0.02 + 1.0)
        assert out_a.total_cash[0] == pytest.approx(4 * 0.02 + 0.85)

    def test_breach_delivers_worst_performer_scaled_by_strike(self):
        note = make_note(strike_price=80.0)
        # Terminal worst 0.40 < 0.60 barrier: redemption = 0.40 / 0.80 = 0.50
        out = evaluate(note, [[0.9, 0.9, 0.9, 0.40]])
        assert out.breached[0]
        assert out.total_cash[0] == pytest.approx(3 * 0.02 + 0.50)

    def test_capital_protection_floors_redemption(self):
        note = make_note(capital_protection=50.0)
        out = evaluate(note, [[0.9, 0.9, 0.9, 0.30]])
        assert out.breached[0]
        # Floor at 50% beats delivering 30%
        assert out.total_cash[0] == pytest.approx(3 * 0.02 + 0.50)

    def test_full_protection_ignores_barrier(self):
        note = make_note(capital_protection=100.0)
        out = evaluate(note, [[0.3, 0.3, 0.3, 0.30]])
        assert not out.breached[0]
        assert out.total_cash[0] == pytest.approx(1.0)


@pytest.mark.unit
class TestDiscounting:
    def test_hand_computed_pv(self):
        r = 0.05
        note = make_note(
            coupon_type="Fixed",
            coupon_frequency="Semi-Annual",
            protection_barrier=None,
            capital_protection=100.0,
        )
        out = evaluate(note, [[1.0, 1.0]], discount_rate=r)

        schedule = build_observation_schedule(note, as_of=TODAY)
        c = 0.08 / 2
        expected = c * math.exp(-r * schedule[0].t_years) + (c + 1.0) * math.exp(
            -r * schedule[1].t_years
        )
        assert out.pv[0] == pytest.approx(expected, abs=1e-12)
