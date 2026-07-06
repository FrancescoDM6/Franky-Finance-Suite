"""Pure options-chain helpers shared by the Research and Options modules.

No Reflex imports: expiration selection, strike filtering, and DataFrame
row formatting extracted from the research OptionsState so a standalone
options page can reuse them. The research state delegates here.
"""

import logging
from datetime import date, datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def select_default_expiration(
    expirations: List[str],
    profile_timeframe: str,
    today: Optional[date] = None,
) -> str:
    """Select the best default expiration based on user profile.

    - 1_week: first expiration in the 3-10 day range
    - 2_weeks (Conservative): 7-21 days
    - 1_2_months (Aggressive): 30-60 days
    - anything else: first available expiration

    Falls back to the first expiration if no match in the preferred range.
    """
    if not expirations:
        return ""

    today = today or datetime.now().date()

    if profile_timeframe == "1_week":
        min_days, max_days = 3, 10
    elif profile_timeframe == "2_weeks":
        min_days, max_days = 7, 21
    elif profile_timeframe == "1_2_months":
        min_days, max_days = 30, 60
    else:
        return expirations[0]

    for exp_str in expirations:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            days_out = (exp_date - today).days
            if min_days <= days_out <= max_days:
                return exp_str
        except ValueError:
            continue

    return expirations[0]


def days_to_expiry(expiration: str, today: Optional[date] = None) -> int:
    """Days from today until an ISO expiration date (0 on parse failure)."""
    today = today or datetime.now().date()
    try:
        exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
        return (exp_date - today).days
    except ValueError:
        return 0


def interesting_strikes(
    strikes: List[float],
    current_price: float,
    range_high: float = 0.0,
    range_low: float = 0.0,
    target_price: float = 0.0,
    limit: int = 8,
) -> List[dict]:
    """Filter to 'interesting' annotated strikes for the research card.

    Returns list of dicts: {strike, annotation, is_atm}.
    """
    if not strikes or not current_price:
        return []

    interesting = []
    seen_strikes = set()

    lower_bound = current_price * 0.90
    upper_bound = current_price * 1.10

    atm_strike = min(strikes, key=lambda x: abs(x - current_price))
    round_interval = 5 if current_price < 100 else 10

    for strike in sorted(strikes):
        if strike < lower_bound or strike > upper_bound:
            continue
        if strike in seen_strikes:
            continue

        annotation = ""
        is_atm = False

        if strike == atm_strike:
            annotation = "ATM"
            is_atm = True
        elif range_high and abs(strike - range_high) / range_high < 0.02:
            annotation = "Range High"
        elif range_low and abs(strike - range_low) / range_low < 0.02:
            annotation = "Range Low"
        elif target_price and abs(strike - target_price) / target_price < 0.02:
            annotation = "Target"
        elif strike % round_interval == 0:
            annotation = "Round"
        else:
            continue

        seen_strikes.add(strike)
        interesting.append(
            {"strike": strike, "annotation": annotation, "is_atm": is_atm}
        )

    if atm_strike not in seen_strikes:
        interesting.append(
            {"strike": atm_strike, "annotation": "ATM", "is_atm": True}
        )

    interesting.sort(key=lambda x: x["strike"])
    return interesting[:limit]


def strikes_around_atm(
    strikes: List[float], spot: float, count: int = 13
) -> List[dict]:
    """Contiguous strike window centered on ATM for a trading chain view.

    Unlike interesting_strikes (research-curated annotations), a trading
    chain wants a dense window around the money. Returns the same
    {strike, annotation, is_atm} shape with "" annotations except ATM.
    """
    if not strikes or not spot:
        return []

    ordered = sorted(set(strikes))
    atm_idx = min(range(len(ordered)), key=lambda i: abs(ordered[i] - spot))

    half = count // 2
    start = max(0, atm_idx - half)
    end = min(len(ordered), start + count)
    start = max(0, end - count)

    return [
        {
            "strike": s,
            "annotation": "ATM" if i == atm_idx else "",
            "is_atm": i == atm_idx,
        }
        for i, s in ((i, ordered[i]) for i in range(start, end))
    ]


def format_chain_rows(
    df,
    strikes: List[float],
    strike_info: dict,
    option_type: str,
) -> List[dict]:
    """Format options DataFrame rows for display.

    Adds a "mid" key ((bid+ask)/2, falling back bid -> ask -> 0.0) used by
    the options module to prefill trade premiums.
    """
    rows = []

    if df is None or df.empty:
        return rows

    filtered = df[df["strike"].isin(strikes)]

    for _, row in filtered.iterrows():
        strike = row["strike"]
        info = strike_info.get(strike, {})
        iv_raw = float(row.get("impliedVolatility", 0) or 0)
        bid = float(row.get("bid", 0) or 0)
        ask = float(row.get("ask", 0) or 0)
        if bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
        else:
            mid = bid or ask or 0.0

        rows.append(
            {
                "strike": float(strike),
                "bid": bid,
                "ask": ask,
                "mid": round(mid, 2),
                "oi": int(row.get("openInterest", 0) or 0),
                "iv": iv_raw,
                "iv_pct": f"{iv_raw * 100:.0f}%",  # Pre-formatted for display
                "annotation": info.get("annotation", ""),
                "is_atm": info.get("is_atm", False),
            }
        )

    # Sort calls descending (high strikes first), puts ascending
    if option_type == "call":
        rows.sort(key=lambda x: x["strike"], reverse=True)
    else:
        rows.sort(key=lambda x: x["strike"])

    return rows
