"""Pure form <-> StructuredNote conversion for the Notes module.

No Reflex imports: everything here is plain Python so it can be unit
tested directly. The state layer keeps form fields as strings; this
module owns parsing and validation.
"""

from datetime import date
from typing import Dict, List, Optional

from ...models.structured_note import ObservationDate, StructuredNote

COUPON_FREQUENCIES = ["Monthly", "Quarterly", "Semi-Annual", "Annual"]
COUPON_TYPES = ["Fixed", "Contingent", "Memory"]
BARRIER_TYPES = ["European", "American"]

# Form field name -> StructuredNote population is centralized here so the
# state layer can stay a dumb string container.
FORM_DEFAULTS: Dict[str, str] = {
    "issuer": "",
    "product_name": "",
    "tickers": "",
    "currency": "USD",
    "notional": "1000",
    "maturity_date": "",
    "coupon_rate": "",
    "coupon_frequency": "Quarterly",
    "coupon_type": "Contingent",
    "coupon_barrier": "",
    "autocall_barrier": "",
    "protection_barrier": "",
    "barrier_type": "European",
    "strike": "100",
    "capital_protection": "0",
}


class FormValidationError(ValueError):
    """A user-correctable problem with the terms form."""


def _required_float(value: str, label: str, lo: float, hi: float) -> float:
    try:
        parsed = float(value.strip())
    except (ValueError, AttributeError):
        raise FormValidationError(f"{label} must be a number")
    if not (lo <= parsed <= hi):
        raise FormValidationError(f"{label} must be between {lo:g} and {hi:g}")
    return parsed


def _optional_float(value: str, label: str, lo: float, hi: float) -> Optional[float]:
    if value is None or not value.strip():
        return None
    return _required_float(value, label, lo, hi)


def build_note_from_form(
    fields: Dict[str, str],
    observation_dates: Optional[List[ObservationDate]] = None,
) -> StructuredNote:
    """Validate form fields and build a StructuredNote.

    Raises:
        FormValidationError: with a user-facing message on the first
            invalid field encountered.
    """
    tickers = [
        t.strip().upper()
        for t in (fields.get("tickers") or "").replace(";", ",").split(",")
        if t.strip()
    ]
    if not tickers:
        raise FormValidationError("At least one underlying ticker is required")

    maturity_raw = (fields.get("maturity_date") or "").strip()
    if not maturity_raw:
        raise FormValidationError("Maturity date is required (YYYY-MM-DD)")
    try:
        maturity = date.fromisoformat(maturity_raw)
    except ValueError:
        raise FormValidationError("Maturity date must be YYYY-MM-DD")
    if maturity <= date.today():
        raise FormValidationError("Maturity date must be in the future")

    coupon_rate = _required_float(
        fields.get("coupon_rate") or "", "Coupon rate (% p.a.)", 0.0, 100.0
    )

    frequency = fields.get("coupon_frequency") or "Quarterly"
    if frequency not in COUPON_FREQUENCIES:
        raise FormValidationError(f"Coupon frequency must be one of {COUPON_FREQUENCIES}")
    coupon_type = fields.get("coupon_type") or "Contingent"
    if coupon_type not in COUPON_TYPES:
        raise FormValidationError(f"Coupon type must be one of {COUPON_TYPES}")
    barrier_type = fields.get("barrier_type") or "European"
    if barrier_type not in BARRIER_TYPES:
        raise FormValidationError(f"Barrier type must be one of {BARRIER_TYPES}")

    return StructuredNote(
        issuer=(fields.get("issuer") or "").strip(),
        product_name=(fields.get("product_name") or "").strip(),
        underlying_tickers=tickers,
        maturity_date=maturity,
        currency=(fields.get("currency") or "USD").strip().upper() or "USD",
        notional_amount=_optional_float(
            fields.get("notional") or "", "Notional", 1.0, 1e9
        )
        or 1000.0,
        capital_protection=_optional_float(
            fields.get("capital_protection") or "", "Capital protection %", 0.0, 100.0
        )
        or 0.0,
        strike_price=_optional_float(fields.get("strike") or "", "Strike %", 1.0, 200.0),
        coupon_rate_pa=coupon_rate,
        coupon_frequency=frequency,
        coupon_type=coupon_type,
        coupon_barrier=_optional_float(
            fields.get("coupon_barrier") or "", "Coupon barrier %", 1.0, 200.0
        ),
        autocall_barrier=_optional_float(
            fields.get("autocall_barrier") or "", "Autocall barrier %", 1.0, 200.0
        ),
        protection_barrier=_optional_float(
            fields.get("protection_barrier") or "", "Protection barrier %", 1.0, 200.0
        ),
        barrier_type=barrier_type,
        observation_dates=observation_dates or [],
    )


def form_from_note(note: StructuredNote) -> Dict[str, str]:
    """Convert a (possibly partial) parsed note into form field strings."""

    def num(value, default: str = "") -> str:
        if value is None:
            return default
        return f"{value:g}"

    return {
        "issuer": note.issuer or "",
        "product_name": note.product_name or "",
        "tickers": ", ".join(note.underlying_tickers),
        "currency": note.currency or "USD",
        "notional": num(note.notional_amount, "1000"),
        "maturity_date": note.maturity_date.isoformat() if note.maturity_date else "",
        "coupon_rate": num(note.coupon_rate_pa),
        "coupon_frequency": note.coupon_frequency,
        "coupon_type": note.coupon_type,
        "coupon_barrier": num(note.coupon_barrier),
        "autocall_barrier": num(note.autocall_barrier),
        "protection_barrier": num(note.protection_barrier),
        "barrier_type": note.barrier_type,
        "strike": num(note.strike_price, "100"),
        "capital_protection": num(note.capital_protection, "0"),
    }
