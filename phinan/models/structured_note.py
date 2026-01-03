"""Structured Note Data Models.

Defines the structure for parsed structured note parameters.
"""

from datetime import date
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class ObservationDate(BaseModel):
    """Observation date with associated trigger levels."""
    date: date
    autocall_trigger: Optional[float] = None  # % of initial strike
    coupon_trigger: Optional[float] = None    # % of initial strike (if different from autocall)
    
class StructuredNote(BaseModel):
    """Core parameters extracted from a Structured Note term sheet."""
    
    # Identification
    isin: Optional[str] = None
    issuer: str = Field(..., description="Bank or issuer name")
    product_name: str = Field(..., description="Marketing name of the product")
    
    # Underlying Assets
    underlying_tickers: List[str] = Field(..., description="List of underlying stock tickers")
    initial_fixing_date: Optional[date] = None
    final_fixing_date: Optional[date] = None
    maturity_date: Optional[date] = None
    
    # Economics
    currency: str = "USD"
    notional_amount: float = 1000.0
    capital_protection: float = Field(0.0, description="Capital protection % (0-100)")
    strike_price: Optional[float] = Field(None, description="Strike price as % of initial fixing")
    
    # Coupon Details
    coupon_rate_pa: float = Field(..., description="Annualized coupon rate in %")
    coupon_frequency: Literal["Monthly", "Quarterly", "Semi-Annual", "Annual"] = "Quarterly"
    coupon_type: Literal["Fixed", "Contingent", "Memory"] = "Contingent"
    coupon_barrier: Optional[float] = Field(None, description="Barrier level for coupon payment %")
    
    # Risk Features
    autocall_barrier: Optional[float] = Field(None, description="Initial autocall barrier level %")
    protection_barrier: Optional[float] = Field(None, description="Final capital protection barrier %")
    barrier_type: Literal["European", "American"] = Field("European", description="European (at maturity) or American (daily close) barrier")
    
    # Dates
    observation_dates: List[ObservationDate] = []
    
    # Pricing/Valuation (Calculated, not parsed)
    estimated_value: Optional[float] = None
    implied_fee: Optional[float] = None
    
class NoteValuation(BaseModel):
    """Valuation result for a note."""
    fair_value_pct: float
    bond_floor_pct: float
    option_value_pct: float
    implied_fee_pct: float
    break_even_pct: float
    probability_of_loss: float
    probability_of_autocall: float
