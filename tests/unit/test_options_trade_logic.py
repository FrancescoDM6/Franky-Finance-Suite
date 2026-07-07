"""Unit tests for options trade P/L and performance analytics."""

from datetime import datetime

import pytest

from phinan.modules.options.trade_logic import (
    compute_performance,
    compute_realized_pnl,
    format_trades_for_prompt,
    holding_days,
)


@pytest.mark.unit
class TestRealizedPnl:
    def test_long_win(self):
        # Bought at 3.55, sold at 4.75, 2 contracts
        assert compute_realized_pnl("long", 3.55, 4.75, 2) == pytest.approx(240.0)

    def test_long_loss(self):
        assert compute_realized_pnl("long", 3.55, 1.00, 1) == pytest.approx(-255.0)

    def test_short_win(self):
        # Sold at 2.00, bought back at 0.50
        assert compute_realized_pnl("short", 2.00, 0.50, 1) == pytest.approx(150.0)

    def test_short_loss(self):
        assert compute_realized_pnl("short", 2.00, 5.00, 1) == pytest.approx(-300.0)

    def test_expired_worthless_long_loses_premium(self):
        assert compute_realized_pnl("long", 3.55, 0.0, 1) == pytest.approx(-355.0)

    def test_expired_worthless_short_keeps_premium(self):
        assert compute_realized_pnl("short", 3.55, 0.0, 1) == pytest.approx(355.0)


@pytest.mark.unit
class TestHoldingDays:
    def test_positive(self):
        days = holding_days(datetime(2026, 7, 1), datetime(2026, 7, 10))
        assert days == 9

    def test_never_negative(self):
        days = holding_days(datetime(2026, 7, 10), datetime(2026, 7, 1))
        assert days == 0


def trade(pnl, strategy="long_call", ticker="AAPL", opened="2026-07-01", closed="2026-07-10"):
    return {
        "realized_pnl": pnl,
        "strategy": strategy,
        "ticker_symbol": ticker,
        "opened_at": opened,
        "closed_at": closed,
    }


@pytest.mark.unit
class TestComputePerformance:
    def test_known_four_trade_set(self):
        # Wins: +200, +100 -> avg_win 150; losses: -100, -50 -> avg_loss 75
        # win_rate 0.5; expectancy = 150*0.5 - 75*0.5 = 37.5; total +150
        trades = [trade(200.0), trade(100.0), trade(-100.0), trade(-50.0)]

        perf = compute_performance(trades)

        assert perf["trade_count"] == 4
        assert perf["win_rate"] == pytest.approx(0.5)
        assert perf["avg_win"] == pytest.approx(150.0)
        assert perf["avg_loss"] == pytest.approx(75.0)
        assert perf["expectancy"] == pytest.approx(37.5)
        assert perf["total_pnl"] == pytest.approx(150.0)
        assert perf["avg_holding_days"] == pytest.approx(9.0)

    def test_zero_pnl_counts_as_loss(self):
        perf = compute_performance([trade(0.0), trade(100.0)])
        assert perf["win_count"] == 1
        assert perf["loss_count"] == 1
        assert perf["win_rate"] == pytest.approx(0.5)

    def test_all_winners(self):
        perf = compute_performance([trade(100.0), trade(50.0)])
        assert perf["win_rate"] == pytest.approx(1.0)
        assert perf["avg_loss"] == 0.0
        assert perf["expectancy"] == pytest.approx(75.0)

    def test_all_losers(self):
        perf = compute_performance([trade(-100.0), trade(-50.0)])
        assert perf["win_rate"] == 0.0
        assert perf["expectancy"] == pytest.approx(-75.0)

    def test_empty_returns_sentinel(self):
        assert compute_performance([]) == {"trade_count": 0}

    def test_breakdowns_group_and_sort(self):
        trades = [
            trade(300.0, strategy="covered_call", ticker="ORCL"),
            trade(-100.0, strategy="long_call", ticker="NVDA"),
            trade(50.0, strategy="covered_call", ticker="ORCL"),
        ]
        perf = compute_performance(trades)

        by_strategy = perf["by_strategy"]
        assert by_strategy[0]["key"] == "covered_call"  # highest total first
        assert by_strategy[0]["count"] == 2
        assert by_strategy[0]["total_pnl"] == pytest.approx(350.0)
        assert by_strategy[0]["win_rate"] == pytest.approx(1.0)
        assert by_strategy[0]["label"] == "Covered Call"

        by_underlying = perf["by_underlying"]
        assert by_underlying[0]["key"] == "ORCL"
        assert by_underlying[1]["key"] == "NVDA"


@pytest.mark.unit
class TestPromptFormatting:
    def test_formats_and_truncates(self):
        trades = [
            dict(
                trade(240.0),
                strike_price=185.0,
                expiration_date="2026-07-17",
                quantity=2,
                premium=3.55,
                exit_price=4.75,
                status="closed",
            )
        ] * 25

        block = format_trades_for_prompt(trades, limit=20)

        lines = block.splitlines()
        assert len(lines) == 20
        assert "AAPL long_call K=185.0" in lines[0]
        assert "+$240" in lines[0]
        assert "held 9d" in lines[0]
