"""Unit tests for the Monte Carlo engine (seeded/deterministic cases)."""

from datetime import date, timedelta

import pytest

from phinan.config.settings import settings
from phinan.models.structured_note import StructuredNote
from phinan.services.structured_products.bond_floor import closed_form_bond_floor
from phinan.services.structured_products.engine import MarketInputs, simulate_note

TODAY = date(2026, 7, 1)


def make_note(**overrides) -> StructuredNote:
    defaults = dict(
        issuer="Test Bank",
        product_name="Test Autocallable",
        underlying_tickers=["AAA"],
        maturity_date=TODAY + timedelta(days=730),
        coupon_rate_pa=8.0,
        coupon_frequency="Quarterly",
        coupon_type="Contingent",
        coupon_barrier=70.0,
        autocall_barrier=100.0,
        protection_barrier=60.0,
        barrier_type="European",
        capital_protection=0.0,
        strike_price=100.0,
    )
    defaults.update(overrides)
    return StructuredNote(**defaults)


def make_market(tickers=("AAA",), vol=0.2, rho=0.6) -> MarketInputs:
    return MarketInputs(
        spots={t: 100.0 for t in tickers},
        vols={t: vol for t in tickers},
        risk_free_rate=0.045,
        credit_spread=0.01,
        correlation=rho,
    )


@pytest.mark.unit
class TestDeterministicLimits:
    def test_zero_vol_protected_fixed_note_equals_bond_floor(self):
        note = make_note(
            coupon_type="Fixed",
            capital_protection=100.0,
            autocall_barrier=None,
            protection_barrier=None,
        )
        market = make_market(vol=0.0)

        result, _ = simulate_note(note, market, n_paths=100, seed=1, as_of=TODAY)

        floor = closed_form_bond_floor(note, 0.045 + 0.01, as_of=TODAY)
        assert result.fair_value_pct == pytest.approx(floor, abs=1e-4)
        assert result.prob_loss == 0.0
        assert result.prob_barrier_breach == 0.0

    def test_zero_vol_autocalls_at_first_observation(self):
        # With r > 0 and zero vol, the level drifts above 100% immediately
        note = make_note(autocall_barrier=100.0)
        market = make_market(vol=0.0)

        result, _ = simulate_note(note, market, n_paths=100, seed=1, as_of=TODAY)

        assert result.prob_autocall == pytest.approx(1.0)
        assert result.autocall_by_date[0].probability == pytest.approx(1.0)
        assert result.expected_life_years == pytest.approx(0.25, abs=0.02)


@pytest.mark.unit
class TestStatisticalProperties:
    def test_seed_reproducibility_is_exact(self):
        note = make_note()
        market = make_market()

        r1, w1 = simulate_note(note, market, n_paths=2_000, seed=42, as_of=TODAY)
        r2, w2 = simulate_note(note, market, n_paths=2_000, seed=42, as_of=TODAY)

        assert r1.fair_value_pct == r2.fair_value_pct
        assert r1.percentiles == r2.percentiles
        assert (w1 == w2).all()

    def test_different_seeds_differ(self):
        note = make_note()
        market = make_market()

        r1, _ = simulate_note(note, market, n_paths=2_000, seed=1, as_of=TODAY)
        r2, _ = simulate_note(note, market, n_paths=2_000, seed=2, as_of=TODAY)

        assert r1.fair_value_pct != r2.fair_value_pct

    def test_percentiles_are_monotonic(self):
        note = make_note()
        market = make_market(vol=0.35)

        result, _ = simulate_note(note, market, n_paths=4_000, seed=7, as_of=TODAY)

        p = result.percentiles
        assert p["p5"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p95"]

    def test_histogram_covers_all_paths(self):
        note = make_note()
        market = make_market(vol=0.35)

        result, _ = simulate_note(note, market, n_paths=4_000, seed=7, as_of=TODAY)

        total_pct = sum(b.pct for b in result.histogram)
        assert 99.0 <= total_pct <= 101.0

    def test_worst_of_basket_is_worth_less(self):
        # A worst-of on two uncorrelated assets carries more downside risk
        # than the same note on a single asset
        single = make_note(underlying_tickers=["AAA"])
        double = make_note(underlying_tickers=["AAA", "BBB"])

        r_single, _ = simulate_note(
            single, make_market(("AAA",), vol=0.3), n_paths=6_000, seed=3, as_of=TODAY
        )
        r_double, _ = simulate_note(
            double,
            make_market(("AAA", "BBB"), vol=0.3, rho=0.1),
            n_paths=6_000,
            seed=3,
            as_of=TODAY,
        )

        assert r_double.fair_value_pct < r_single.fair_value_pct
        assert r_double.prob_barrier_breach > r_single.prob_barrier_breach

    def test_american_barrier_breaches_at_least_as_often(self):
        euro = make_note(barrier_type="European")
        amer = make_note(barrier_type="American")
        market = make_market(vol=0.3)

        r_e, _ = simulate_note(euro, market, n_paths=4_000, seed=11, as_of=TODAY)
        r_a, _ = simulate_note(amer, market, n_paths=4_000, seed=11, as_of=TODAY)

        assert r_a.prob_barrier_breach >= r_e.prob_barrier_breach


@pytest.mark.unit
class TestGuardrails:
    def test_path_count_is_clamped(self):
        note = make_note()
        market = make_market()
        cap = settings.structured_products.max_paths

        result, worst = simulate_note(
            note, market, n_paths=cap + 10_000, seed=1, as_of=TODAY
        )

        assert result.n_paths == cap
        assert len(worst) == cap

    def test_no_tickers_raises(self):
        note = make_note(underlying_tickers=[])
        with pytest.raises(ValueError, match="tickers"):
            simulate_note(note, make_market(), n_paths=100, seed=1, as_of=TODAY)

    def test_missing_vol_raises(self):
        note = make_note(underlying_tickers=["AAA", "ZZZ"])
        with pytest.raises(ValueError, match="ZZZ"):
            simulate_note(note, make_market(("AAA",)), n_paths=100, seed=1, as_of=TODAY)

    def test_audit_trail_recorded(self):
        note = make_note()
        market = make_market()

        result, _ = simulate_note(note, market, n_paths=500, seed=99, as_of=TODAY)

        assert result.seed == 99
        assert result.n_paths == 500
        assert result.risk_free_rate == pytest.approx(0.045)
        assert result.vols_used == {"AAA": 0.2}
