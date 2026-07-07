"""Unit tests for single-leg options analytics (Black-Scholes math)."""

import math

import pytest

from phinan.services.options_analytics import (
    break_even,
    bs_greeks,
    bs_price,
    max_profit_loss,
    payoff_at_price,
    payoff_curve,
    preview_strategy,
    probability_of_profit,
    strategy_label,
)

# Textbook parameters: S=100, K=100, sigma=0.2, r=0.05, T=1
S, K, SIGMA, R, T = 100.0, 100.0, 0.2, 0.05, 1.0


@pytest.mark.unit
class TestBlackScholesPrice:
    def test_call_matches_textbook_value(self):
        assert bs_price(S, K, SIGMA, R, T, "call") == pytest.approx(10.4506, abs=1e-3)

    def test_put_matches_textbook_value(self):
        assert bs_price(S, K, SIGMA, R, T, "put") == pytest.approx(5.5735, abs=1e-3)

    def test_put_call_parity(self):
        call = bs_price(S, 95.0, 0.3, 0.04, 2.0, "call")
        put = bs_price(S, 95.0, 0.3, 0.04, 2.0, "put")
        assert call - put == pytest.approx(S - 95.0 * math.exp(-0.04 * 2.0), abs=1e-9)

    def test_zero_time_falls_back_to_intrinsic(self):
        assert bs_price(110, 100, SIGMA, R, 0.0, "call") == pytest.approx(10.0)
        assert bs_price(90, 100, 0.0, R, T, "put") == pytest.approx(10.0)


@pytest.mark.unit
class TestGreeks:
    def test_call_greeks_match_known_values(self):
        greeks = bs_greeks(S, K, SIGMA, R, T, "call")
        assert greeks.delta == pytest.approx(0.6368, abs=1e-4)
        assert greeks.gamma == pytest.approx(0.018762, abs=1e-5)
        assert greeks.vega == pytest.approx(0.3752, abs=1e-3)  # per 1 vol point
        assert greeks.theta < 0  # long options decay

    def test_put_delta_is_call_delta_minus_one(self):
        call = bs_greeks(S, K, SIGMA, R, T, "call")
        put = bs_greeks(S, K, SIGMA, R, T, "put")
        assert put.delta == pytest.approx(call.delta - 1.0, abs=1e-12)
        assert put.gamma == pytest.approx(call.gamma, abs=1e-12)

    def test_degenerate_inputs_return_none(self):
        assert bs_greeks(S, K, 0.0, R, T, "call") is None
        assert bs_greeks(S, K, SIGMA, R, 0.0, "call") is None


@pytest.mark.unit
class TestPayoff:
    def test_break_even(self):
        assert break_even(185.0, 3.55, "call") == pytest.approx(188.55)
        assert break_even(185.0, 3.55, "put") == pytest.approx(181.45)

    def test_payoff_all_four_combinations(self):
        # At S_T = 200, K = 185, premium = 3.55, 1 contract
        args = (185.0, 3.55)
        assert payoff_at_price(200, *args, "call", "long", 1) == pytest.approx(1145.0)
        assert payoff_at_price(200, *args, "call", "short", 1) == pytest.approx(-1145.0)
        assert payoff_at_price(200, *args, "put", "long", 1) == pytest.approx(-355.0)
        assert payoff_at_price(200, *args, "put", "short", 1) == pytest.approx(355.0)

    def test_payoff_scales_with_contracts(self):
        one = payoff_at_price(200, 185.0, 3.55, "call", "long", 1)
        three = payoff_at_price(200, 185.0, 3.55, "call", "long", 3)
        assert three == pytest.approx(3 * one)

    def test_curve_includes_strike_and_break_even(self):
        curve = payoff_curve(185.0, 185.0, 3.55, "call", "long", 1)
        prices = [point["price"] for point in curve]
        assert 185.0 in prices
        assert 188.55 in prices
        # Break-even point has ~zero P/L
        be_point = next(p for p in curve if p["price"] == 188.55)
        assert be_point["pnl"] == pytest.approx(0.0, abs=0.01)

    def test_curve_is_sorted_and_bounded(self):
        curve = payoff_curve(100.0, 100.0, 2.0, "put", "short", 1, pct_range=0.30)
        prices = [point["price"] for point in curve]
        assert prices == sorted(prices)
        assert prices[0] >= 100.0 * 0.70 - 0.01
        assert prices[-1] <= 100.0 * 1.30 + 0.01


@pytest.mark.unit
class TestMaxProfitLoss:
    def test_long_call_unlimited_profit(self):
        profit, loss = max_profit_loss(185.0, 3.55, "call", "long", 1)
        assert profit is None
        assert loss == pytest.approx(355.0)

    def test_short_call_unlimited_loss(self):
        profit, loss = max_profit_loss(185.0, 3.55, "call", "short", 1)
        assert profit == pytest.approx(355.0)
        assert loss is None

    def test_long_put_bounded_both_sides(self):
        profit, loss = max_profit_loss(100.0, 4.0, "put", "long", 2)
        assert profit == pytest.approx((100.0 - 4.0) * 100 * 2)
        assert loss == pytest.approx(800.0)

    def test_short_put_bounded_both_sides(self):
        profit, loss = max_profit_loss(100.0, 4.0, "put", "short", 1)
        assert profit == pytest.approx(400.0)
        assert loss == pytest.approx(9600.0)


@pytest.mark.unit
class TestProbabilityOfProfit:
    def test_long_atm_call_pop_below_half(self):
        # Premium pushes break-even above spot: less than a coin flip
        pop = probability_of_profit(S, K, 5.0, SIGMA, R, T, "call", "long")
        assert pop is not None
        assert pop < 0.5

    def test_deep_itm_short_put_pop_near_one(self):
        # Short put struck far below spot almost always keeps the premium
        pop = probability_of_profit(S, 50.0, 0.5, SIGMA, R, T, "put", "short")
        assert pop > 0.95

    def test_long_and_short_complement(self):
        long_pop = probability_of_profit(S, K, 3.0, SIGMA, R, T, "call", "long")
        short_pop = probability_of_profit(S, K, 3.0, SIGMA, R, T, "call", "short")
        assert long_pop + short_pop == pytest.approx(1.0, abs=1e-9)

    def test_degenerate_inputs_return_none(self):
        assert probability_of_profit(S, K, 3.0, 0.0, R, T, "call", "long") is None
        assert probability_of_profit(S, K, 3.0, SIGMA, R, 0.0, "call", "long") is None


@pytest.mark.unit
class TestStrategyLabelAndPreview:
    def test_strategy_label_mapping(self):
        assert strategy_label("call", "long") == "long_call"
        assert strategy_label("put", "long") == "long_put"
        assert strategy_label("call", "short") == "covered_call"
        assert strategy_label("put", "short") == "cash_secured_put"

    def test_preview_bundle_shape(self):
        preview = preview_strategy(S, 185.0, 3.55, "call", "long", 1, SIGMA, R, 0.25)
        assert preview["entry_amount"] == pytest.approx(355.0)
        assert preview["is_debit"] is True
        assert preview["break_even"] == pytest.approx(188.55)
        assert preview["unlimited_profit"] is True
        assert preview["max_profit"] is None
        assert preview["max_loss"] == pytest.approx(355.0)
        assert 0.0 <= preview["pop"] <= 1.0
        assert set(preview["greeks"]) == {"delta", "gamma", "theta", "vega"}
        assert len(preview["payoff"]) >= 61

    def test_short_position_flips_greek_signs(self):
        long_p = preview_strategy(S, K, 3.0, "call", "long", 1, SIGMA, R, T)
        short_p = preview_strategy(S, K, 3.0, "call", "short", 1, SIGMA, R, T)
        assert short_p["greeks"]["delta"] == pytest.approx(
            -long_p["greeks"]["delta"], abs=1e-9
        )
        assert short_p["is_debit"] is False
