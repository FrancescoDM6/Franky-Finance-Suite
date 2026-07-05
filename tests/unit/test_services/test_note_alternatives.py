"""Unit tests for the alternatives comparison and Black-Scholes helpers."""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from phinan.models.structured_note import SimulationResult, StructuredNote
from phinan.services.structured_products.alternatives import (
    bs_call,
    bs_put,
    compare_alternatives,
)
from phinan.services.structured_products.engine import MarketInputs


def make_note() -> StructuredNote:
    return StructuredNote(
        issuer="Test",
        product_name="Note",
        underlying_tickers=["AAA"],
        maturity_date=date.today() + timedelta(days=365),
        coupon_rate_pa=8.0,
        capital_protection=0.0,
    )


def make_simulation() -> SimulationResult:
    return SimulationResult(
        fair_value_pct=0.95,
        bond_floor_pct=0.9,
        option_value_pct=0.05,
        implied_fee_pct=0.05,
        expected_return_pct=0.06,
        expected_irr=0.06,
        median_irr=0.07,
        prob_autocall=0.5,
        prob_barrier_breach=0.2,
        prob_loss=0.15,
        expected_life_years=1.0,
        percentiles={"p5": -0.25, "p25": 0.0, "p50": 0.07, "p75": 0.08, "p95": 0.08},
    )


def make_market(vol: float = 0.2, r: float = 0.045) -> MarketInputs:
    return MarketInputs(
        spots={"AAA": 100.0},
        vols={"AAA": vol},
        risk_free_rate=r,
        credit_spread=0.01,
        correlation=0.6,
    )


@pytest.mark.unit
class TestBlackScholes:
    def test_call_matches_known_value(self):
        # Classic textbook value: S=K=1, sigma=0.2, r=0, T=1 -> ~0.0797
        assert bs_call(1.0, 1.0, 0.2, 0.0, 1.0) == pytest.approx(0.0797, abs=1e-3)

    def test_put_call_parity(self):
        s, k, sigma, r, t = 1.0, 0.95, 0.3, 0.04, 2.0
        call = bs_call(s, k, sigma, r, t)
        put = bs_put(s, k, sigma, r, t)
        assert call - put == pytest.approx(s - k * math.exp(-r * t), abs=1e-9)

    def test_zero_time_is_intrinsic(self):
        assert bs_call(1.1, 1.0, 0.2, 0.05, 0.0) == pytest.approx(0.1)
        assert bs_put(0.9, 1.0, 0.2, 0.05, 0.0) == pytest.approx(0.1)


@pytest.mark.unit
class TestCompareAlternatives:
    def test_returns_four_rows_in_order(self):
        rows = compare_alternatives(
            make_note(), make_market(), make_simulation(),
            np.full(1000, 1.05), 1.0,
        )
        strategies = [r.strategy for r in rows]
        assert strategies == [
            "This note",
            "Direct equity (worst-of)",
            "Covered calls (monthly)",
            "Risk-free bond",
        ]

    def test_note_row_restates_simulation(self):
        sim = make_simulation()
        rows = compare_alternatives(
            make_note(), make_market(), sim, np.full(1000, 1.05), 1.0
        )
        note_row = rows[0]
        assert note_row.expected_irr == sim.expected_irr
        assert note_row.p5 == sim.percentiles["p5"]
        assert note_row.max_loss_pct == -1.0  # no capital protection

    def test_equity_row_from_synthetic_terminals(self):
        # Deterministic terminals: half at +20%, half at -10%
        terminals = np.array([1.2] * 500 + [0.9] * 500)
        rows = compare_alternatives(
            make_note(), make_market(), make_simulation(), terminals, 1.0
        )
        equity = rows[1]
        assert equity.expected_return_pct == pytest.approx(0.05, abs=1e-9)
        assert equity.max_loss_pct == pytest.approx(-0.1)
        assert equity.p5 == pytest.approx(-0.1)
        assert equity.p95 == pytest.approx(0.2)

    def test_covered_call_caps_upside_and_adds_premium(self):
        # A single huge-upside terminal: covered call must cap it
        terminals = np.full(100, 2.0)
        rows = compare_alternatives(
            make_note(), make_market(vol=0.2), make_simulation(), terminals, 1.0
        )
        covered = rows[2]
        equity = rows[1]
        assert covered.expected_return_pct < equity.expected_return_pct
        # But income means it beats holding cash at zero
        assert covered.expected_return_pct > 0.0

    def test_risk_free_row_is_deterministic(self):
        r = 0.05
        rows = compare_alternatives(
            make_note(), make_market(r=r), make_simulation(),
            np.full(100, 1.0), 2.0,
        )
        rf = rows[3]
        expected_total = math.exp(r * 2.0) - 1.0
        assert rf.expected_return_pct == pytest.approx(expected_total, abs=1e-4)
        assert rf.p5 == rf.p50 == rf.p95
        assert rf.max_loss_pct == 0.0

    def test_every_heuristic_row_has_a_caveat(self):
        rows = compare_alternatives(
            make_note(), make_market(), make_simulation(), np.full(100, 1.0), 1.0
        )
        assert all(r.caveat for r in rows)
