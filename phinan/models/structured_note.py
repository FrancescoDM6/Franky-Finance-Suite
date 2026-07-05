"""Structured Note Data Models.

Defines the structure for parsed structured note parameters and the
Monte Carlo analysis results computed from them.
"""

import datetime
from datetime import date
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class ObservationDate(BaseModel):
    """Observation date with associated trigger levels."""
    date: date
    autocall_trigger: Optional[float] = None  # % of initial strike
    coupon_trigger: Optional[float] = None    # % of initial strike (if different from autocall)

class StructuredNote(BaseModel):
    """Core parameters extracted from a Structured Note term sheet.

    Fields the LLM frequently misses have defaults rather than being
    required: a partially parsed note must still hydrate the correction
    form (the term-accuracy loop is the safety net, not this schema).
    """

    # Identification
    isin: Optional[str] = None
    issuer: str = Field("", description="Bank or issuer name")
    product_name: str = Field("", description="Marketing name of the product")

    # Underlying Assets
    underlying_tickers: List[str] = Field(
        default_factory=list, description="List of underlying stock tickers"
    )
    initial_fixing_date: Optional[date] = None
    final_fixing_date: Optional[date] = None
    maturity_date: Optional[date] = None
    
    # Economics
    currency: str = "USD"
    notional_amount: float = 1000.0
    capital_protection: float = Field(0.0, description="Capital protection % (0-100)")
    strike_price: Optional[float] = Field(None, description="Strike price as % of initial fixing")
    
    # Coupon Details
    coupon_rate_pa: float = Field(0.0, description="Annualized coupon rate in %")
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
    
class AutocallProbability(BaseModel):
    """Probability of autocall at a single observation date."""

    # datetime.date qualified: a bare `date` annotation would resolve to
    # this field's own None default in the class namespace (pydantic
    # evaluates hints with the class locals)
    date: Optional[datetime.date] = None
    t_years: float
    probability: float          # P(autocalled exactly at this observation)
    cumulative: float           # P(autocalled at or before this observation)


class OutcomeBucket(BaseModel):
    """One bucket of the simulated total-return histogram."""

    label: str                  # e.g. "-12% to -8%"
    low: float                  # bucket lower bound (total return, fraction)
    high: float                 # bucket upper bound
    pct: float                  # % of paths landing in this bucket (0-100)


class SimulationResult(BaseModel):
    """Monte Carlo valuation and risk metrics for a structured note.

    All *_pct value fields are fractions of notional (1.0 = 100%).
    Probabilities are fractions (0-1). Returns are fractions.
    """

    # Valuation decomposition
    fair_value_pct: float
    bond_floor_pct: float       # closed-form PV of protected principal + fixed coupons
    option_value_pct: float     # fair_value - bond_floor (net coupon/short-put component)
    implied_fee_pct: float      # 1.0 - fair_value (issuer margin at par issue)

    # Return metrics (annualized simple returns per path)
    expected_return_pct: float  # mean total return over the note's life
    expected_irr: float         # mean annualized return
    median_irr: float

    # Risk probabilities
    prob_autocall: float
    prob_barrier_breach: float
    prob_loss: float            # P(total cash received < notional)
    expected_life_years: float

    # Distribution
    percentiles: Dict[str, float] = Field(
        default_factory=dict,
        description="Total-return percentiles keyed p5/p25/p50/p75/p95",
    )
    autocall_by_date: List[AutocallProbability] = Field(default_factory=list)
    histogram: List[OutcomeBucket] = Field(default_factory=list)

    # Input audit trail (what the simulation actually used)
    n_paths: int = 0
    seed: Optional[int] = None
    risk_free_rate: float = 0.0
    credit_spread: float = 0.0
    correlation_used: float = 0.0
    vols_used: Dict[str, float] = Field(default_factory=dict)
    spots_used: Dict[str, float] = Field(default_factory=dict)


class AlternativeResult(BaseModel):
    """Outcome summary of one alternative strategy for comparison."""

    strategy: str
    expected_return_pct: float  # total return over the same horizon (fraction)
    expected_irr: float         # annualized (fraction)
    max_loss_pct: float         # worst simulated/possible total return (fraction, <= 0)
    p5: float
    p50: float
    p95: float
    caveat: str = ""            # honest note about the approximation used


class NoteAnalysis(BaseModel):
    """The full persisted analysis bundle for a structured note."""

    note: StructuredNote
    simulation: SimulationResult
    alternatives: List[AlternativeResult] = Field(default_factory=list)
    narrative: str = ""
