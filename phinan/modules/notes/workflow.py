"""Notes workflow orchestration, packaged as a Reflex state mixin.

NotesWorkflowMixin holds the async event handlers that drive the module:
PDF upload -> LLM extraction -> fill the editable terms form (analysis
never auto-runs; the user corrects terms first), then run_analysis builds
the note from the form, fetches market inputs, and runs the Monte Carlo
engine. It is mixed into NotesState (see state.py).
"""

import logging
from typing import List

import reflex as rx

from ...core.async_utils import run_sync
from ...models.structured_note import ObservationDate
from . import form_logic

logger = logging.getLogger(__name__)


class NotesWorkflowMixin(rx.State, mixin=True):
    """Async orchestration event handlers for the Notes module."""

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Extract a term sheet PDF and populate the terms form.

        Deliberately does NOT run the analysis: LLM extraction is
        fallible, so the user reviews/corrects the form first.
        """
        from ...services import services

        if not files:
            return

        file = files[0]
        self.is_parsing = True
        self.error_message = ""
        self.form_error = ""
        self.parse_warnings = []
        self.source_filename = file.name or ""
        yield

        try:
            content = await file.read()
            text = await run_sync(services.pdf_parser.extract_text, content)
            if not text.strip():
                self.error_message = (
                    "No text could be extracted from this PDF. Scanned/image "
                    "PDFs are not supported yet - enter the terms manually."
                )
                return
            yield

            note, warnings = await run_sync(
                services.pdf_parser.parse_term_sheet, text
            )
            if note is None:
                self.error_message = (
                    warnings[0]
                    if warnings
                    else "Could not extract terms - enter them manually."
                )
                return

            self._apply_form_fields(form_logic.form_from_note(note))
            self._parsed_observation_dates = [
                od.model_dump(mode="json") for od in note.observation_dates
            ]
            self.parse_warnings = warnings
            self.terms_dirty = bool(self.has_analysis)

        except Exception as e:
            logger.error("Note upload error: %s", e)
            self.error_message = f"Upload failed: {e}"
        finally:
            self.is_parsing = False

    async def run_analysis(self):
        """Validate the terms form and run the Monte Carlo analysis."""
        from ...services import services

        self.form_error = ""
        self.error_message = ""

        # 1. Build the note from the form (pure validation)
        try:
            observation_dates = [
                ObservationDate.model_validate(od)
                for od in self._parsed_observation_dates
            ]
            note = form_logic.build_note_from_form(
                self._form_fields(), observation_dates
            )
        except form_logic.FormValidationError as e:
            self.form_error = str(e)
            return

        self._analysis_generation += 1
        generation = self._analysis_generation
        self.is_analyzing = True
        self.analysis_stage = "Fetching market data..."
        yield

        try:
            # 2. Market inputs (spots + realized vols + rate overrides)
            try:
                market = await run_sync(
                    services.structured_products.build_market_inputs,
                    note,
                    rf_override=self._parse_override(self.override_risk_free),
                    spread_override=self._parse_override(self.override_credit_spread),
                )
            except ValueError as e:
                if generation == self._analysis_generation:
                    self.error_message = str(e)
                return

            if generation != self._analysis_generation:
                return

            n_paths = int(self.n_paths_choice or 10_000)
            self.analysis_stage = f"Simulating {n_paths:,} paths..."
            yield

            # 3. Monte Carlo analysis
            analysis = await run_sync(
                services.structured_products.analyze_note,
                note,
                market=market,
                n_paths=n_paths,
            )

            if generation != self._analysis_generation:
                return

            self._store_analysis(analysis)
            self.terms_dirty = False

        except Exception as e:
            logger.error("Note analysis error: %s", e)
            if generation == self._analysis_generation:
                self.error_message = f"Analysis failed: {e}"
        finally:
            if generation == self._analysis_generation:
                self.is_analyzing = False
                self.analysis_stage = ""

    def _store_analysis(self, analysis) -> None:
        """Store a NoteAnalysis as JSON-safe dicts (lean state)."""
        sim = analysis.simulation.model_dump(mode="json")
        self.outcome_histogram = sim.pop("histogram", [])
        self.autocall_timeline = sim.pop("autocall_by_date", [])
        self.simulation = sim
        self.alternatives = [
            alt.model_dump(mode="json") for alt in analysis.alternatives
        ]
        self.narrative = analysis.narrative or ""

    def _form_fields(self) -> dict:
        """Collect the current form field values."""
        return {
            "issuer": self.form_issuer,
            "product_name": self.form_product_name,
            "tickers": self.form_tickers,
            "currency": self.form_currency,
            "notional": self.form_notional,
            "maturity_date": self.form_maturity_date,
            "coupon_rate": self.form_coupon_rate,
            "coupon_frequency": self.form_coupon_frequency,
            "coupon_type": self.form_coupon_type,
            "coupon_barrier": self.form_coupon_barrier,
            "autocall_barrier": self.form_autocall_barrier,
            "protection_barrier": self.form_protection_barrier,
            "barrier_type": self.form_barrier_type,
            "strike": self.form_strike,
            "capital_protection": self.form_capital_protection,
        }

    def _apply_form_fields(self, fields: dict) -> None:
        """Populate the form vars from a field dict."""
        self.form_issuer = fields.get("issuer", "")
        self.form_product_name = fields.get("product_name", "")
        self.form_tickers = fields.get("tickers", "")
        self.form_currency = fields.get("currency", "USD")
        self.form_notional = fields.get("notional", "1000")
        self.form_maturity_date = fields.get("maturity_date", "")
        self.form_coupon_rate = fields.get("coupon_rate", "")
        self.form_coupon_frequency = fields.get("coupon_frequency", "Quarterly")
        self.form_coupon_type = fields.get("coupon_type", "Contingent")
        self.form_coupon_barrier = fields.get("coupon_barrier", "")
        self.form_autocall_barrier = fields.get("autocall_barrier", "")
        self.form_protection_barrier = fields.get("protection_barrier", "")
        self.form_barrier_type = fields.get("barrier_type", "European")
        self.form_strike = fields.get("strike", "100")
        self.form_capital_protection = fields.get("capital_protection", "0")

    @staticmethod
    def _parse_override(value: str):
        """Parse an advanced override entered in percent, or None."""
        if not value or not value.strip():
            return None
        try:
            return float(value.strip()) / 100.0
        except ValueError:
            return None

    def set_form_field(self, field: str, value: str):
        """Generic form field setter: marks results stale after edits."""
        attr = f"form_{field}"
        if not hasattr(self, attr):
            logger.warning("Unknown notes form field: %s", field)
            return
        setattr(self, attr, value)
        self.form_error = ""
        if self.has_analysis:
            self.terms_dirty = True

    def clear_all(self):
        """Reset the module to a blank manual-entry form."""
        self._apply_form_fields(dict(form_logic.FORM_DEFAULTS))
        self._parsed_observation_dates = []
        self.parse_warnings = []
        self.error_message = ""
        self.form_error = ""
        self.analysis_stage = ""
        self.terms_dirty = False
        self.source_filename = ""
        self.simulation = {}
        self.outcome_histogram = []
        self.autocall_timeline = []
        self.alternatives = []
        self.narrative = ""
