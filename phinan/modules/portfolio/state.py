"""Portfolio state management.

Handles portfolio positions stored in DuckDB.
"""

import json
import os
from datetime import date
from decimal import Decimal
from typing import Optional

import reflex as rx

from ...services import services


class PortfolioPosition(rx.Base):
    """A single portfolio position."""
    id: int = 0
    ticker_symbol: str = ""
    quantity: float = 0.0
    cost_basis: float = 0.0
    purchase_date: str = ""  # ISO format
    notes: str = ""
    # Computed fields (not stored)
    current_price: float = 0.0
    current_value: float = 0.0
    gain_loss: float = 0.0
    gain_loss_percent: float = 0.0


class PortfolioState(rx.State):
    """State for portfolio management."""
    
    # Positions list
    positions: list[PortfolioPosition] = []
    
    # Form inputs for adding positions
    form_ticker: str = ""
    form_quantity: str = ""
    form_cost_basis: str = ""
    form_purchase_date: str = ""
    form_notes: str = ""
    
    # Ticker autocomplete data
    tickers: list[dict] = []
    show_autocomplete: bool = False
    
    # UI state
    is_loading: bool = False
    error_message: str = ""
    show_add_form: bool = False
    
    def load_tickers(self):
        """Load ticker data for autocomplete."""
        if self.tickers:
            return  # Already loaded
        try:
            # Use same ticker data as research module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(current_dir, "..", "research", "data", "tickers.json")
            
            with open(data_path, "r") as f:
                self.tickers = json.load(f)
        except Exception as e:
            print(f"Error loading tickers for portfolio: {e}")
            self.tickers = []
    
    @rx.var
    def ticker_options(self) -> list[str]:
        """Filter tickers based on form input."""
        if not self.form_ticker or len(self.form_ticker) < 1:
            return []
        
        search_term = self.form_ticker.upper()
        options = []
        
        for t in self.tickers:
            if search_term in t.get("symbol", "") or search_term in t.get("name", "").upper():
                options.append(f"{t['symbol']} - {t['name']}")
                if len(options) >= 8:
                    break
        
        return options
    
    def set_form_ticker(self, value: str):
        """Handle ticker input change."""
        self.form_ticker = value.upper()
        self.show_autocomplete = len(self.form_ticker) >= 1 and len(self.ticker_options) > 0
    
    def select_ticker(self, option: str):
        """Select a ticker from autocomplete dropdown."""
        # Extract symbol from "SYMBOL - Name" format
        if " - " in option:
            self.form_ticker = option.split(" - ")[0]
        else:
            self.form_ticker = option
        self.show_autocomplete = False
    
    # Summary computed values
    @rx.var
    def total_value(self) -> float:
        """Total current value of all positions."""
        return sum(p.current_value for p in self.positions)
    
    @rx.var
    def total_cost(self) -> float:
        """Total cost basis of all positions."""
        return sum(p.quantity * p.cost_basis for p in self.positions)
    
    @rx.var
    def total_gain_loss(self) -> float:
        """Total unrealized gain/loss."""
        return self.total_value - self.total_cost
    
    @rx.var
    def total_gain_loss_percent(self) -> float:
        """Total gain/loss as percentage."""
        if self.total_cost == 0:
            return 0.0
        return (self.total_gain_loss / self.total_cost) * 100
    
    @rx.var
    def has_positions(self) -> bool:
        """Whether user has any positions."""
        return len(self.positions) > 0
    
    def toggle_add_form(self):
        """Toggle add position form visibility."""
        self.show_add_form = not self.show_add_form
        if not self.show_add_form:
            self._clear_form()
    
    def _clear_form(self):
        """Clear the add position form."""
        self.form_ticker = ""
        self.form_quantity = ""
        self.form_cost_basis = ""
        self.form_purchase_date = ""
        self.form_notes = ""
        self.error_message = ""
    
    async def load_positions(self):
        """Load all positions from database with current prices."""
        self.is_loading = True
        self.error_message = ""
        
        try:
            # Query positions from database
            result = services.db.query(
                """
                SELECT id, ticker_symbol, quantity, cost_basis, purchase_date, notes
                FROM portfolio
                ORDER BY ticker_symbol
                """
            )
            
            positions = []
            for row in result:
                pos = PortfolioPosition(
                    id=row["id"],
                    ticker_symbol=row["ticker_symbol"],
                    quantity=float(row["quantity"]),
                    cost_basis=float(row["cost_basis"]),
                    purchase_date=str(row["purchase_date"]) if row["purchase_date"] else "",
                    notes=row["notes"] or "",
                )
                
                # Fetch current price
                try:
                    info = services.market_data.get_ticker_info(pos.ticker_symbol)
                    if info and info.current_price:
                        pos.current_price = info.current_price
                        pos.current_value = pos.quantity * pos.current_price
                        total_cost = pos.quantity * pos.cost_basis
                        pos.gain_loss = pos.current_value - total_cost
                        if total_cost > 0:
                            pos.gain_loss_percent = (pos.gain_loss / total_cost) * 100
                except Exception:
                    # If price fetch fails, use cost basis
                    pos.current_price = pos.cost_basis
                    pos.current_value = pos.quantity * pos.cost_basis
                
                positions.append(pos)
            
            self.positions = positions
            
        except Exception as e:
            self.error_message = f"Error loading positions: {str(e)}"
        finally:
            self.is_loading = False
    
    async def add_position(self):
        """Add a new position to the portfolio."""
        self.error_message = ""
        
        # Validate inputs
        if not self.form_ticker.strip():
            self.error_message = "Ticker symbol is required"
            return
        
        try:
            quantity = float(self.form_quantity)
            if quantity <= 0:
                self.error_message = "Quantity must be positive"
                return
        except ValueError:
            self.error_message = "Invalid quantity"
            return
        
        try:
            cost_basis = float(self.form_cost_basis)
            if cost_basis <= 0:
                self.error_message = "Cost basis must be positive"
                return
        except ValueError:
            self.error_message = "Invalid cost basis"
            return
        
        # Parse date or use today
        purchase_date = self.form_purchase_date.strip() or date.today().isoformat()
        
        ticker = self.form_ticker.strip().upper()
        
        try:
            # Insert into database
            services.db.execute(
                """
                INSERT INTO portfolio (ticker_symbol, quantity, cost_basis, purchase_date, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ticker, quantity, cost_basis, purchase_date, self.form_notes.strip())
            )
            
            # Clear form and reload positions
            self._clear_form()
            self.show_add_form = False
            await self.load_positions()
            
        except Exception as e:
            self.error_message = f"Error adding position: {str(e)}"
    
    async def delete_position(self, position_id: int):
        """Delete a position from the portfolio."""
        try:
            services.db.execute(
                "DELETE FROM portfolio WHERE id = ?",
                (position_id,)
            )
            await self.load_positions()
        except Exception as e:
            self.error_message = f"Error deleting position: {str(e)}"
    
    def get_position_for_ticker(self, ticker: str) -> Optional[PortfolioPosition]:
        """Get position for a specific ticker (for Research integration)."""
        ticker = ticker.upper()
        for pos in self.positions:
            if pos.ticker_symbol == ticker:
                return pos
        return None
    
    @rx.var
    def position_tickers(self) -> list[str]:
        """List of tickers in portfolio (for quick lookup)."""
        return [p.ticker_symbol for p in self.positions]
