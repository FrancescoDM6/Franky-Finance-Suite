"""Unit tests for the extracted pure options-chain helpers."""

from datetime import date

import pandas as pd
import pytest

from phinan.modules.research.options_logic import (
    days_to_expiry,
    format_chain_rows,
    interesting_strikes,
    select_default_expiration,
    strikes_around_atm,
)

TODAY = date(2026, 7, 1)


@pytest.mark.unit
class TestSelectDefaultExpiration:
    EXPIRATIONS = ["2026-07-03", "2026-07-10", "2026-07-17", "2026-08-14", "2026-10-16"]

    def test_two_weeks_profile_picks_7_to_21_days(self):
        result = select_default_expiration(self.EXPIRATIONS, "2_weeks", today=TODAY)
        assert result == "2026-07-10"  # 9 days out

    def test_one_two_months_profile_picks_30_to_60_days(self):
        result = select_default_expiration(self.EXPIRATIONS, "1_2_months", today=TODAY)
        assert result == "2026-08-14"  # 44 days out

    def test_unknown_profile_uses_first(self):
        result = select_default_expiration(self.EXPIRATIONS, "varies", today=TODAY)
        assert result == self.EXPIRATIONS[0]

    def test_no_match_falls_back_to_first(self):
        result = select_default_expiration(["2027-01-15"], "2_weeks", today=TODAY)
        assert result == "2027-01-15"

    def test_empty_returns_empty(self):
        assert select_default_expiration([], "2_weeks", today=TODAY) == ""


@pytest.mark.unit
class TestDaysToExpiry:
    def test_counts_days(self):
        assert days_to_expiry("2026-07-15", today=TODAY) == 14

    def test_bad_date_returns_zero(self):
        assert days_to_expiry("soon", today=TODAY) == 0


@pytest.mark.unit
class TestInterestingStrikes:
    def test_annotates_atm_and_round(self):
        strikes = [170.0, 175.0, 180.0, 182.5, 185.0, 190.0, 195.0]
        result = interesting_strikes(strikes, current_price=181.0)

        atm = [s for s in result if s["is_atm"]]
        assert len(atm) == 1
        assert atm[0]["strike"] == 180.0
        assert all(s["annotation"] for s in result)

    def test_limits_count(self):
        strikes = [float(s) for s in range(150, 220, 5)]
        result = interesting_strikes(strikes, current_price=185.0, limit=8)
        assert len(result) <= 8

    def test_empty_without_price(self):
        assert interesting_strikes([100.0], current_price=0.0) == []


@pytest.mark.unit
class TestStrikesAroundAtm:
    def test_window_centered_on_atm(self):
        strikes = [float(s) for s in range(100, 210, 5)]
        result = strikes_around_atm(strikes, spot=152.0, count=7)

        assert len(result) == 7
        atm = [s for s in result if s["is_atm"]]
        assert len(atm) == 1
        assert atm[0]["strike"] == 150.0
        values = [s["strike"] for s in result]
        assert values == sorted(values)
        assert 150.0 in values

    def test_window_clamps_at_edges(self):
        strikes = [95.0, 100.0, 105.0]
        result = strikes_around_atm(strikes, spot=96.0, count=13)
        assert [s["strike"] for s in result] == [95.0, 100.0, 105.0]

    def test_empty_inputs(self):
        assert strikes_around_atm([], 100.0) == []
        assert strikes_around_atm([100.0], 0.0) == []


@pytest.mark.unit
class TestFormatChainRows:
    def _df(self, rows):
        return pd.DataFrame(rows)

    def test_formats_and_computes_mid(self):
        df = self._df(
            [
                {"strike": 100.0, "bid": 3.0, "ask": 3.5, "openInterest": 12,
                 "impliedVolatility": 0.42},
            ]
        )
        rows = format_chain_rows(df, [100.0], {100.0: {"annotation": "ATM", "is_atm": True}}, "call")

        assert rows[0]["mid"] == pytest.approx(3.25)
        assert rows[0]["iv_pct"] == "42%"
        assert rows[0]["is_atm"] is True

    def test_mid_falls_back_bid_then_ask(self):
        df = self._df(
            [
                {"strike": 100.0, "bid": 2.0, "ask": 0.0, "openInterest": 0,
                 "impliedVolatility": 0.3},
                {"strike": 105.0, "bid": 0.0, "ask": 1.5, "openInterest": 0,
                 "impliedVolatility": 0.3},
                {"strike": 110.0, "bid": 0.0, "ask": 0.0, "openInterest": 0,
                 "impliedVolatility": 0.3},
            ]
        )
        rows = format_chain_rows(df, [100.0, 105.0, 110.0], {}, "put")

        by_strike = {r["strike"]: r for r in rows}
        assert by_strike[100.0]["mid"] == pytest.approx(2.0)
        assert by_strike[105.0]["mid"] == pytest.approx(1.5)
        assert by_strike[110.0]["mid"] == pytest.approx(0.0)

    def test_calls_sorted_descending_puts_ascending(self):
        df = self._df(
            [
                {"strike": s, "bid": 1.0, "ask": 1.2, "openInterest": 1,
                 "impliedVolatility": 0.3}
                for s in [100.0, 110.0, 105.0]
            ]
        )
        calls = format_chain_rows(df, [100.0, 105.0, 110.0], {}, "call")
        puts = format_chain_rows(df, [100.0, 105.0, 110.0], {}, "put")

        assert [r["strike"] for r in calls] == [110.0, 105.0, 100.0]
        assert [r["strike"] for r in puts] == [100.0, 105.0, 110.0]

    def test_empty_df(self):
        assert format_chain_rows(pd.DataFrame(), [100.0], {}, "call") == []
