"""State for the Structured Notes module.

Handles PDF file upload, parsing, and valuation logic.
"""

import logging
from typing import List, Optional

import reflex as rx

from ...core.async_utils import run_sync
from ...models.structured_note import StructuredNote, NoteValuation
from ...services import services

logger = logging.getLogger(__name__)

class NoteState(rx.State):
    """State for the Notes module."""
    
    # Upload State
    is_uploading: bool = False
    upload_progress: int = 0
    parsing_status: str = "" # "Parsing PDF...", "Analyzing Structure...", "Valuing Note..."
    error_message: str = ""
    
    # Analysis Results
    parsed_note: Optional[StructuredNote] = None
    valuation: Optional[NoteValuation] = None
    
    # UI Toggles
    show_details: bool = False
    
    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle PDF file upload."""
        if not files:
            return
            
        file = files[0]
        self.is_uploading = True
        self.upload_progress = 10
        self.parsing_status = "Reading PDF..."
        self.error_message = ""
        self.parsed_note = None
        self.valuation = None
        
        try:
            # Read file content
            content = await file.read()
            
            self.upload_progress = 30
            self.parsing_status = "Extracting Text (AI)..."
            yield
            
            # 1. Parse PDF
            # Note: We pass bytes content to the service
            text = await run_sync(services.pdf_parser.extract_text, content)
            if not text:
                raise ValueError("Could not extract text from PDF")
                
            self.upload_progress = 50
            self.parsing_status = "Structure Analysis..."
            yield
                
            # 2. Extract Structure using LLM
            note = await run_sync(services.pdf_parser.parse_term_sheet, text)
            if not note:
                raise ValueError("Could not parse term sheet parameters")
                
            self.parsed_note = note
            
            self.upload_progress = 80
            self.parsing_status = "Running Valuation Models..."
            yield
            
            # 3. Valuation
            valuation = await run_sync(
                services.structured_products.calculate_fair_value, note
            )
            self.valuation = valuation
            
            self.upload_progress = 100
            self.parsing_status = "Complete"
            self.show_details = True
            
        except Exception as e:
            self.error_message = f"Error: {str(e)}"
            logger.error("Note upload error: %s", e)
        finally:
            self.is_uploading = False
            
    def clear_analysis(self):
        """Reset the analysis state."""
        self.parsed_note = None
        self.valuation = None
        self.error_message = ""
        self.upload_progress = 0
        self.parsing_status = ""
        self.show_details = False

    @rx.var
    def has_results(self) -> bool:
        return self.parsed_note is not None and self.valuation is not None
        
    @rx.var
    def implied_fee_color(self) -> str:
        """Color code for implied fee."""
        if not self.valuation:
            return "gray"
        fee = self.valuation.implied_fee_pct
        if fee < 0.015:
            return "green"
        elif fee < 0.025:
            return "amber"
        else:
            return "red"
            
    @rx.var
    def bond_floor_label(self) -> str:
        if not self.valuation:
            return "N/A"
        return f"{self.valuation.bond_floor_pct * 100:.2f}%"
        
    @rx.var
    def note_summary(self) -> str:
        """Brief summary of the note."""
        if not self.parsed_note:
            return ""
        return f"{self.parsed_note.issuer} {self.parsed_note.product_name} ({self.parsed_note.coupon_rate_pa}% p.a.)"

    @rx.var
    def underlying_tickers_display(self) -> str:
        """Comma-separated list of underlying tickers."""
        if not self.parsed_note:
            return ""
        return ", ".join(self.parsed_note.underlying_tickers)

    @rx.var
    def note_issuer(self) -> str:
        return self.parsed_note.issuer if self.parsed_note else ""

    @rx.var
    def note_strike(self) -> str:
        if not self.parsed_note or self.parsed_note.strike_price is None:
            return ""
        return f"{self.parsed_note.strike_price}%"

    @rx.var
    def note_barrier(self) -> str:
        if not self.parsed_note:
            return ""
        return f"{self.parsed_note.protection_barrier}% ({self.parsed_note.barrier_type})"

    @rx.var
    def note_coupon(self) -> str:
        if not self.parsed_note:
            return ""
        return f"{self.parsed_note.coupon_rate_pa}% p.a. ({self.parsed_note.coupon_frequency})"

    @rx.var
    def note_autocall(self) -> str:
        if not self.parsed_note:
            return ""
        return f"{self.parsed_note.autocall_barrier}%"

    @rx.var
    def option_value_display(self) -> str:
        """Option value percentage for display."""
        if not self.valuation:
            return "N/A"
        return f"{self.valuation.option_value_pct * 100:.2f}%"

    @rx.var
    def fair_value_display(self) -> str:
        """Fair value percentage for display."""
        if not self.valuation:
            return "N/A"
        return f"{self.valuation.fair_value_pct * 100:.2f}%"

    @rx.var
    def implied_fee_display(self) -> str:
        """Implied fee percentage for display."""
        if not self.valuation:
            return "N/A"
        return f"{self.valuation.implied_fee_pct * 100:.2f}%"
