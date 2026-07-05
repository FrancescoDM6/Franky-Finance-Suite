"""Computed display vars for the Notes module, as Reflex state mixins.

Read-only formatting over the simulation result dict stored in state.
"""

from typing import Any

import reflex as rx


def _pct(value: Any, decimals: int = 1, signed: bool = False) -> str:
    """Format a fraction as a percentage string."""
    if value is None:
        return "N/A"
    sign = "+" if signed and value >= 0 else ""
    return f"{sign}{value * 100:.{decimals}f}%"


class ValuationVarsMixin(rx.State, mixin=True):
    """Formatting for the valuation and risk cards."""

    @rx.var
    def has_analysis(self) -> bool:
        return bool(self.simulation)

    @rx.var
    def fmt_fair_value(self) -> str:
        return _pct(self.simulation.get("fair_value_pct"))

    @rx.var
    def fmt_bond_floor(self) -> str:
        return _pct(self.simulation.get("bond_floor_pct"))

    @rx.var
    def fmt_option_value(self) -> str:
        return _pct(self.simulation.get("option_value_pct"), signed=True)

    @rx.var
    def fmt_implied_fee(self) -> str:
        return _pct(self.simulation.get("implied_fee_pct"))

    @rx.var
    def implied_fee_color(self) -> str:
        """Color-code the embedded fee (green < 1.5%, amber < 3%, red)."""
        fee = self.simulation.get("implied_fee_pct")
        if fee is None:
            return "gray"
        if fee < 0.015:
            return "green"
        if fee < 0.03:
            return "amber"
        return "red"

    @rx.var
    def fmt_expected_irr(self) -> str:
        return _pct(self.simulation.get("expected_irr"), signed=True)

    @rx.var
    def fmt_median_irr(self) -> str:
        return _pct(self.simulation.get("median_irr"), signed=True)

    @rx.var
    def fmt_prob_autocall(self) -> str:
        return _pct(self.simulation.get("prob_autocall"), decimals=0)

    @rx.var
    def fmt_prob_breach(self) -> str:
        return _pct(self.simulation.get("prob_barrier_breach"), decimals=0)

    @rx.var
    def fmt_prob_loss(self) -> str:
        return _pct(self.simulation.get("prob_loss"), decimals=0)

    @rx.var
    def prob_loss_color(self) -> str:
        p = self.simulation.get("prob_loss")
        if p is None:
            return "gray"
        if p < 0.10:
            return "green"
        if p < 0.25:
            return "amber"
        return "red"

    @rx.var
    def fmt_expected_life(self) -> str:
        life = self.simulation.get("expected_life_years")
        return f"{life:.1f} years" if life is not None else "N/A"

    @rx.var
    def percentile_rows(self) -> list[dict]:
        """Total-return percentiles as label/value rows for the risk card."""
        p = self.simulation.get("percentiles") or {}
        labels = [
            ("p5", "Bottom 5%"),
            ("p25", "Bottom 25%"),
            ("p50", "Median"),
            ("p75", "Top 25%"),
            ("p95", "Top 5%"),
        ]
        return [
            {"label": label, "value": _pct(p.get(key), signed=True)}
            for key, label in labels
            if key in p
        ]

    @rx.var
    def audit_footnote(self) -> str:
        """What the simulation actually used (transparency footnote)."""
        sim = self.simulation
        if not sim:
            return ""
        vols = sim.get("vols_used") or {}
        vol_str = ", ".join(f"{t} {v * 100:.0f}%" for t, v in vols.items())
        parts = [
            f"{sim.get('n_paths', 0):,} paths",
            f"risk-free {_pct(sim.get('risk_free_rate'), 2)}",
            f"credit spread {_pct(sim.get('credit_spread'), 2)}",
        ]
        if vol_str:
            parts.append(f"vol: {vol_str}")
        if len(vols) > 1:
            parts.append(f"correlation {sim.get('correlation_used', 0):.2f}")
        return "Simulation inputs: " + " | ".join(parts)


class TermsVarsMixin(rx.State, mixin=True):
    """Small helpers for the terms form and parse feedback."""

    @rx.var
    def has_parse_warnings(self) -> bool:
        return len(self.parse_warnings) > 0

    @rx.var
    def coupon_needs_barrier(self) -> bool:
        """Contingent/Memory coupons need a coupon barrier to matter."""
        return self.form_coupon_type != "Fixed"
