"""Prompt builders for the Notes module.

Every number is preformatted here in Python; the LLM explains, it never
computes (per the "LLM extracts, Python calculates" rule).
"""

from typing import List


def _pct(value, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def build_note_narrative_prompt(
    note: dict,
    simulation: dict,
    alternatives: List[dict],
    profile_name: str,
    profile_description: str,
) -> str:
    """Build the "Phin's Take" narrative prompt from computed facts only."""
    tickers = ", ".join(note.get("underlying_tickers") or []) or "unknown underlyings"
    percentiles = simulation.get("percentiles") or {}

    note_facts = "\n".join(
        [
            f"- Product: {note.get('product_name') or 'structured note'} "
            f"from {note.get('issuer') or 'unknown issuer'}",
            f"- Underlyings (worst-of): {tickers}",
            f"- Coupon: {note.get('coupon_rate_pa', 0)}% p.a. "
            f"({note.get('coupon_type')}, {note.get('coupon_frequency')})",
            f"- Protection barrier: {note.get('protection_barrier') or 'none'}% "
            f"({note.get('barrier_type')})",
            f"- Autocall barrier: {note.get('autocall_barrier') or 'none'}%",
            f"- Maturity: {note.get('maturity_date') or 'unknown'}",
        ]
    )

    sim_facts = "\n".join(
        [
            f"- Fair value: {_pct(simulation.get('fair_value_pct'))} of purchase "
            f"price (embedded fee {_pct(simulation.get('implied_fee_pct'))})",
            f"- Expected annualized return: {_pct(simulation.get('expected_irr'))}",
            f"- Probability of early autocall: {_pct(simulation.get('prob_autocall'), 0)}",
            f"- Probability the barrier is breached: "
            f"{_pct(simulation.get('prob_barrier_breach'), 0)}",
            f"- Probability of losing money: {_pct(simulation.get('prob_loss'), 0)}",
            f"- Expected holding period: "
            f"{simulation.get('expected_life_years', 0):.1f} years",
            f"- Worst 5% of outcomes: {_pct(percentiles.get('p5'))} total return",
            f"- Median outcome: {_pct(percentiles.get('p50'))} total return",
        ]
    )

    alt_lines = "\n".join(
        f"- {alt.get('strategy')}: expected {_pct(alt.get('expected_irr'))} "
        f"annualized, worst 5% {_pct(alt.get('p5'))}"
        for alt in alternatives
    )

    return f"""You are Phin, a personal finance analyst explaining a structured note
to its potential buyer in plain language.

USER PROFILE: {profile_name} - {profile_description}

NOTE TERMS:
{note_facts}

SIMULATION RESULTS (computed by a Monte Carlo model - treat as ground truth):
{sim_facts}

ALTERNATIVES OVER THE SAME HORIZON:
{alt_lines}

Write a short assessment (under 250 words, markdown, 2-3 short sections):
1. What this note actually is, in one plain-language sentence.
2. The trade-off: what you give up and what you get, using the numbers above.
3. What your market outlook would have to be for this note to beat the
   alternatives listed.

STRICT RULES:
- Use ONLY the numbers provided above. Do not compute, estimate, or invent
  any figure.
- No buy/do-not-buy verdict. Frame it as trade-offs and required outlook.
- No greetings or filler; start directly with the content.
"""
