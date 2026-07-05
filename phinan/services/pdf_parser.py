"""PDF Parser Service for Structured Notes.

Extracts text from PDFs and structures it into StructuredNote objects
using the LLM. The LLM only extracts; all normalization and validation
happens in pure Python (note_from_llm_json), which returns the note plus
a list of human-readable warnings for the correction form.
"""

import json
import logging
from datetime import date
from io import BytesIO
from typing import Optional, Tuple

import pypdf

from ..models.structured_note import ObservationDate, StructuredNote

logger = logging.getLogger(__name__)

# Term sheets bury observation tables deep; give the LLM enough text
MAX_PROMPT_CHARS = 12_000

FREQUENCY_ALIASES = {
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "semi-annual": "Semi-Annual",
    "semiannual": "Semi-Annual",
    "semi annual": "Semi-Annual",
    "semi-annually": "Semi-Annual",
    "annual": "Annual",
    "annually": "Annual",
    "yearly": "Annual",
}

COUPON_TYPE_ALIASES = {
    "fixed": "Fixed",
    "guaranteed": "Fixed",
    "contingent": "Contingent",
    "conditional": "Contingent",
    "memory": "Memory",
    "snowball": "Memory",
}

BARRIER_TYPE_ALIASES = {
    "european": "European",
    "american": "American",
    "continuous": "American",
    "daily": "American",
    "at maturity": "European",
}


def _parse_date(value, field: str, warnings: list) -> Optional[date]:
    """Parse an ISO date string defensively, warning instead of raising."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        warnings.append(f"Could not parse {field} '{value}' - please fill it in")
        return None


def _parse_float(value, field: str, warnings: list) -> Optional[float]:
    """Parse a numeric field defensively."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        warnings.append(f"Could not parse {field} '{value}' - please check it")
        return None


def _normalize_enum(value, aliases: dict, default: str, field: str, warnings: list) -> str:
    """Map free-text enum values onto the model's Literal choices."""
    if not value:
        return default
    normalized = aliases.get(str(value).strip().lower())
    if normalized:
        return normalized
    warnings.append(f"Unrecognized {field} '{value}' - defaulted to {default}")
    return default


def note_from_llm_json(data: dict) -> Tuple[StructuredNote, list]:
    """Build a StructuredNote from LLM-extracted JSON.

    Pure and LLM-free so it can be unit tested directly. Never raises on
    bad field values: anything unusable becomes None/default plus a
    warning for the user to correct in the terms form.
    """
    warnings: list = []

    tickers = data.get("underlying_tickers") or []
    if isinstance(tickers, str):
        tickers = [t.strip() for t in tickers.split(",") if t.strip()]
    tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
    if not tickers:
        warnings.append("No underlying tickers found - please add them")

    coupon_rate = _parse_float(data.get("coupon_rate_pa"), "coupon rate", warnings)
    if coupon_rate is None:
        warnings.append("Coupon rate missing - please fill it in")
        coupon_rate = 0.0

    maturity = _parse_date(data.get("maturity_date"), "maturity date", warnings)
    if maturity is None:
        warnings.append("Maturity date missing - required before analysis")

    observation_dates = []
    for od in data.get("observation_dates") or []:
        if not isinstance(od, dict):
            continue
        od_date = _parse_date(od.get("date"), "observation date", warnings)
        if od_date is None:
            continue
        observation_dates.append(
            ObservationDate(
                date=od_date,
                autocall_trigger=_parse_float(
                    od.get("autocall_trigger"), "observation autocall trigger", warnings
                ),
                coupon_trigger=_parse_float(
                    od.get("coupon_trigger"), "observation coupon trigger", warnings
                ),
            )
        )

    note = StructuredNote(
        isin=(str(data["isin"]).strip() if data.get("isin") else None),
        issuer=str(data.get("issuer") or "").strip(),
        product_name=str(data.get("product_name") or "").strip(),
        underlying_tickers=tickers,
        initial_fixing_date=_parse_date(
            data.get("initial_fixing_date"), "initial fixing date", warnings
        ),
        final_fixing_date=_parse_date(
            data.get("final_fixing_date"), "final fixing date", warnings
        ),
        maturity_date=maturity,
        currency=str(data.get("currency") or "USD").strip().upper() or "USD",
        notional_amount=_parse_float(
            data.get("notional_amount"), "notional", warnings
        )
        or 1000.0,
        capital_protection=_parse_float(
            data.get("capital_protection"), "capital protection", warnings
        )
        or 0.0,
        strike_price=_parse_float(data.get("strike_price"), "strike", warnings),
        coupon_rate_pa=coupon_rate,
        coupon_frequency=_normalize_enum(
            data.get("coupon_frequency"),
            FREQUENCY_ALIASES,
            "Quarterly",
            "coupon frequency",
            warnings,
        ),
        coupon_type=_normalize_enum(
            data.get("coupon_type"),
            COUPON_TYPE_ALIASES,
            "Contingent",
            "coupon type",
            warnings,
        ),
        coupon_barrier=_parse_float(
            data.get("coupon_barrier"), "coupon barrier", warnings
        ),
        autocall_barrier=_parse_float(
            data.get("autocall_barrier"), "autocall barrier", warnings
        ),
        protection_barrier=_parse_float(
            data.get("protection_barrier"), "protection barrier", warnings
        ),
        barrier_type=_normalize_enum(
            data.get("barrier_type"),
            BARRIER_TYPE_ALIASES,
            "European",
            "barrier type",
            warnings,
        ),
        observation_dates=observation_dates,
    )
    if not note.issuer:
        warnings.append("Issuer missing")

    return note, warnings


class PDFParserService:
    """Service to handle PDF ingestion and parsing."""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM service to avoid circular imports."""
        if self._llm is None:
            from . import services

            self._llm = services.llm
        return self._llm

    def extract_text(self, file_content: bytes) -> str:
        """Extract raw text from PDF bytes.

        Note: text-based PDFs only; scanned/image PDFs produce no text
        (callers should treat an empty result as an extraction failure).
        """
        try:
            reader = pypdf.PdfReader(BytesIO(file_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error("Error reading PDF: %s", e)
            return ""

    def parse_term_sheet(
        self, text: str
    ) -> Tuple[Optional[StructuredNote], list]:
        """Parse term sheet text into a StructuredNote using the LLM.

        Returns (note, warnings). The note is None only when the LLM is
        unavailable or its output is not JSON at all; partial extractions
        return a note with warnings so the correction form can take over.
        """
        llm = self._get_llm()
        if not llm.health_check():
            logger.warning("LLM service unavailable")
            return None, ["AI extraction unavailable - enter the terms manually"]

        system = (
            "You extract structured product terms from source text. Return JSON only. "
            "Do not estimate or infer missing financial terms unless the source text "
            "directly supports the value. Use null for missing fields."
        )
        prompt = f"""
        You are a financial analyst expert in structured products.
        Extract the key parameters from the following Term Sheet text into JSON format.

        The JSON must match this structure:
        {{
            "issuer": "Bank Name",
            "product_name": "Name of product",
            "underlying_tickers": ["TICKER1", "TICKER2"],
            "isin": "US...",
            "currency": "USD",
            "capital_protection": 0.0,
            "coupon_rate_pa": 10.5,
            "coupon_frequency": "Quarterly",
            "coupon_type": "Contingent",
            "coupon_barrier": 60.0,
            "autocall_barrier": 100.0,
            "protection_barrier": 60.0,
            "strike_price": 100.0,
            "barrier_type": "European",
            "maturity_date": "YYYY-MM-DD",
            "observation_dates": [
                {{"date": "YYYY-MM-DD", "autocall_trigger": 100.0}}
            ]
        }}

        If a field is missing, leave it null. Do not estimate coupon rates, barriers,
        strike prices, dates, currencies, or tickers unless they are supported by the text.
        Standardize frequencies to: Monthly, Quarterly, Semi-Annual, Annual.
        Standardize barriers to % of initial strike (e.g., 60.0 for 60%).

        Text content:
        {text[:MAX_PROMPT_CHARS]}
        """

        try:
            response_text = llm.complete(prompt, system=system)
            json_str = self._clean_json(response_text)
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("LLM returned unparseable JSON: %s", e)
            return None, ["AI extraction returned invalid data - enter the terms manually"]
        except Exception as e:
            logger.error("Error parsing term sheet from LLM: %s", e)
            return None, [f"AI extraction failed: {e}"]

        if not isinstance(data, dict):
            return None, ["AI extraction returned invalid data - enter the terms manually"]

        return note_from_llm_json(data)

    def _clean_json(self, text: str) -> str:
        """Extract JSON from markdown code blocks or surrounding prose."""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        # Balanced-brace fallback: take the outermost {...} span
        first = text.find("{")
        if first != -1:
            depth = 0
            for i in range(first, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[first : i + 1].strip()
        return text.strip()
