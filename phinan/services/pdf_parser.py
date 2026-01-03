"""PDF Parser Service for Structured Notes.

Extracts text from PDFs and helps structure it into Note objects using LLMs.
"""

from io import BytesIO
from typing import Optional
import json
from datetime import date, datetime

import pypdf
from ..models.structured_note import StructuredNote, ObservationDate
from ..config.settings import settings  # Ensure settings access for LLM keys

class PDFParserService:
    """Service to handle PDF ingestion and parsing."""
    
    def __init__(self):
        self._llm = None
        
    def _get_llm(self):
        """Lazy-load LLM service to avoid circular imports."""
        if self._llm is None:
            # Import here to avoid circular dependencies
            from . import services
            self._llm = services.llm
        return self._llm
        
    def extract_text(self, file_content: bytes) -> str:
        """Extract raw text from PDF bytes."""
        try:
            reader = pypdf.PdfReader(BytesIO(file_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return ""

    def parse_term_sheet(self, text: str) -> Optional[StructuredNote]:
        """Parse term sheet text into StructuredNote using LLM."""
        llm = self._get_llm()
        if not llm.health_check():
            print("LLM service unavailable")
            return None
            
        # Prompt for the LLM
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
        
        If a field is missing, estimate it or leave null, but try to infer from context.
        Standardize frequencies to: Monthly, Quarterly, Semi-Annual, Annual.
        Standardize barriers to % of initial strike (e.g., 60.0 for 60%).
        
        Text content:
        {text[:5000]}  # Truncate to avoid context window limits if massive
        """
        
        try:
            # Call LLM
            # We ask for JSON mode from the LLM service if available, or just raw text
            response_text = llm.complete(prompt)
            
            # Clean response to get JSON
            json_str = self._clean_json(response_text)
            
            data = json.loads(json_str)
            
            # Convert date strings to objects
            if "maturity_date" in data and data["maturity_date"]:
                data["maturity_date"] = date.fromisoformat(data["maturity_date"])
                
            if "observation_dates" in data:
                obs_dates = []
                for od in data["observation_dates"]:
                    if "date" in od and od["date"]:
                        od_obj = ObservationDate(
                            date=date.fromisoformat(od["date"]),
                            autocall_trigger=od.get("autocall_trigger"),
                            coupon_trigger=od.get("coupon_trigger")
                        )
                        obs_dates.append(od_obj)
                data["observation_dates"] = obs_dates

            # Create Pydantic model
            return StructuredNote(**data)
            
        except Exception as e:
            print(f"Error parsing term sheet from LLM: {e}")
            return None

    def _clean_json(self, text: str) -> str:
        """Extract JSON from markdown code blocks if present."""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        return text.strip()
