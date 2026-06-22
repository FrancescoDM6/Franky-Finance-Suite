"""Structured Product Valuation Service.

Decomposes structured notes into bond and option components to estimate fair value.
"""

import numpy as np
from scipy.stats import norm
from datetime import date

from ..models.structured_note import StructuredNote, NoteValuation

class StructuredProductService:
    """Service for pricing and analyzing structured products."""
    
    def __init__(self):
        self._market_data = None
    
    def _get_market_data(self):
        if self._market_data is None:
            from . import services
            self._market_data = services.market_data
        return self._market_data

    def calculate_fair_value(self, note: StructuredNote) -> NoteValuation:
        """Calculate fair value breakdown of the note.
        
        Methodology:
        1. Bond Floor: PV of Principal + Fixed Coupons (if any) using Risk-Free Rate + Credit Spread.
        2. Option Component:
           - For Reverse Convertible / Autocallable: Short Down-and-In Put (Barrier Put).
           - Value = Bond Floor - Put Value
        """
        
        # 1. Estimate Bond Floor (Zero Coupon Bond equivalent + PV of coupons if guaranteed)
        # Simplify: Assume Risk Free Rate = 4.5%, Credit Spread = 1.0% (Generic A-rated bank)
        r = 0.045
        spread = 0.01
        discount_rate = r + spread
        
        if not note.maturity_date:
            T = 1.0  # Default to 1 year if missing
        else:
            days = (note.maturity_date - date.today()).days
            T = max(days / 365.0, 0.01)
            
        # Bond Floor (PV of 100% principal at maturity)
        # Note: In real autocallables, duration is uncertain. We use maturity as conservative baseline for risk.
        bond_floor_pct = 1.0 * np.exp(-discount_rate * T)
        
        # 2. Estimate Option Value (Short Barrier Put)
        # This is the "risk" the investor is taking.
        # Investor sells a Put to the bank. The bank pays premium via higher coupons.
        
        # Analytical approximation for Down-and-In Put (Barrier Put)
        # Black-Scholes barrier formula is complex. 
        # Simplify: Plain Vanilla Put value weighted by Probability of Hitting Barrier.
        
        # Parameters
        S = 1.0 # Normalized spot
        K = 1.0 # Normalized strike (usually 100%)
        B = (note.protection_barrier or 60.0) / 100.0 # Barrier level
        sigma = 0.25 # Assume 25% vol for typical autocallable underlying
        
        # Value of a Plain Vanilla Put at Strike K
        d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        put_value = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        # Probability of hitting barrier (Single Touch probability)
        # P(Touch) ~ 2 * P(S_T < barrier) for drift=0 roughly (Reflection principle approximation)
        # This is a rough heuristic for "Down-and-In" probability.
        # A better heuristic for Barrier Put is: Valuation ~ Vanilla Put * (Barrier/Spot)^0.5 approx? 
        # Actually, for deep barriers, the Put value is much lower than Vanilla.
        
        # Let's use a "Barrier Probability" factor
        # Prob(Low < B) over time T
        mu = r - 0.5 * sigma**2
        lambda_val = (mu / sigma**2)
        z = np.log(B/S) / (sigma * np.sqrt(T))
        prob_touch = norm.cdf(z) + (B/S)**(2*lambda_val) * norm.cdf(z - 2*lambda_val*sigma*np.sqrt(T))
        
        # Option Value (The "Premium" the client is selling) takes into account the knock-in
        # For a Reverse Convertible, client is Short Put.
        # Value of Down-In Put
        barrier_put_value_pct = put_value * min(prob_touch * 1.5, 1.0) # Heuristic adjustment
        
        # 3. Fair Value
        # Fair Value = Bond Floor + Coupon PV - Option Risk
        # But wait, Note Price = Bond - Put + Premium(Coupons)
        # Actually simplest view:
        # Client pays 100%.
        # Client receives: Bond + Short Put + Coupon Stream.
        # Fair Value = PV(Bond) + PV(Coupons) - Value(Barrier Put)
        
        coupon_pv = 0.0
        if note.coupon_rate_pa:
            # PV of annuity
            # Assume expected life is until maturity (conservative for valuation) or autcalled (optimistic)
            # Let's use simple PV of coupons for full term for now
            coupon_pct = note.coupon_rate_pa / 100.0
            # PV Annuity factor
            annuity_factor = (1 - (1 + discount_rate)**-T) / discount_rate
            coupon_pv = coupon_pct * annuity_factor
            
        fair_value_pct = bond_floor_pct + coupon_pv - barrier_put_value_pct
        
        # Implied Fee = 100% (Price) - Fair Value
        # If Fair Value is 98%, Fee is 2%.
        implied_fee_pct = max(1.0 - fair_value_pct, 0.0)
        
        return NoteValuation(
            fair_value_pct=round(fair_value_pct, 4),
            bond_floor_pct=round(bond_floor_pct, 4),
            option_value_pct=round(barrier_put_value_pct, 4),
            implied_fee_pct=round(implied_fee_pct, 4),
            break_even_pct=round(1.0 - (note.coupon_rate_pa/100.0 * T), 4), # Roughly
            probability_of_loss=round(prob_touch * 0.4, 4), # Crude approx
            probability_of_autocall=0.6, # Placeholder
        )

