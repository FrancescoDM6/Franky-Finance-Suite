"""Portfolio state management.

Handles portfolio positions stored in DuckDB.
"""

import json
import logging
import os
from datetime import date
from typing import Optional

import reflex as rx
from pydantic import BaseModel

from ...core.async_utils import run_sync
from ...services import services

logger = logging.getLogger(__name__)


class PortfolioPosition(BaseModel):
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
    # Formatted fields for UI (computed during load)
    fmt_quantity: str = ""
    fmt_cost_basis: str = ""
    fmt_current_price: str = ""
    fmt_current_value: str = ""
    fmt_gain_loss: str = ""
    fmt_gain_loss_percent: str = ""
    gain_loss_color: str = "var(--gray-11)"
    gain_loss_badge_color: str = "gray"


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

    # Delete confirmation state
    delete_confirm_position_id: int = 0
    delete_confirm_ticker: str = ""
    show_delete_confirm: bool = False

    def load_tickers(self):
        """Load ticker data for autocomplete."""
        if self.tickers:
            return  # Already loaded
        try:
            # Use same ticker data as research module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(
                current_dir, "..", "research", "data", "tickers.json"
            )

            with open(data_path, "r") as f:
                self.tickers = json.load(f)
        except Exception as e:
            logger.error("Error loading tickers for portfolio: %s", e)
            self.tickers = []

    @rx.var
    def ticker_options(self) -> list[str]:
        """Filter tickers based on form input."""
        if not self.form_ticker or len(self.form_ticker) < 1:
            return []

        search_term = self.form_ticker.upper()
        options = []

        for t in self.tickers:
            if (
                search_term in t.get("symbol", "")
                or search_term in t.get("name", "").upper()
            ):
                options.append(f"{t['symbol']} - {t['name']}")
                if len(options) >= 8:
                    break

        return options

    def set_form_ticker(self, value: str):
        """Handle ticker input change."""
        self.form_ticker = value.upper()
        self.show_autocomplete = (
            len(self.form_ticker) >= 1 and len(self.ticker_options) > 0
        )

    def select_ticker(self, option: str):
        """Select a ticker from autocomplete dropdown."""
        # Extract symbol from "SYMBOL - Name" format
        if " - " in option:
            self.form_ticker = option.split(" - ")[0]
        else:
            self.form_ticker = option
        self.show_autocomplete = False

    def set_form_quantity(self, value: str):
        """Set form quantity."""
        self.form_quantity = value

    def set_form_cost_basis(self, value: str):
        """Set form cost basis."""
        self.form_cost_basis = value

    def set_form_purchase_date(self, value: str):
        """Set form purchase date."""
        self.form_purchase_date = value

    def set_form_notes(self, value: str):
        """Set form notes."""
        self.form_notes = value

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
    def fmt_total_value(self) -> str:
        """Formatted total portfolio value with commas."""
        return f"${self.total_value:,.0f}"

    @rx.var
    def fmt_total_pl_pct(self) -> str:
        """Formatted P/L percentage with sign."""
        sign = "+" if self.total_gain_loss_percent >= 0 else ""
        return f"{sign}{self.total_gain_loss_percent:.1f}%"

    @rx.var
    def fmt_total_cost(self) -> str:
        """Formatted total cost basis."""
        return f"${self.total_cost:,.2f}"

    @rx.var
    def fmt_total_gain_loss(self) -> str:
        """Formatted total gain/loss with sign."""
        if self.total_gain_loss >= 0:
            return f"+${self.total_gain_loss:,.2f}"
        return f"-${abs(self.total_gain_loss):,.2f}"

    @rx.var
    def total_gain_loss_color(self) -> str:
        """CSS color for total gain/loss."""
        return "var(--green-11)" if self.total_gain_loss >= 0 else "var(--red-11)"

    @rx.var
    def total_gain_loss_badge_color(self) -> str:
        """Badge color scheme for total gain/loss."""
        return "green" if self.total_gain_loss >= 0 else "red"

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
        import asyncio

        self.is_loading = True
        self.error_message = ""

        try:
            result = await run_sync(
                services.db.query,
                """
                SELECT id, ticker_symbol, quantity, cost_basis, purchase_date, notes
                FROM portfolio
                ORDER BY ticker_symbol
                """,
            )

            positions = []
            ticker_symbols = []
            for row in result:
                pos = PortfolioPosition(
                    id=row["id"],
                    ticker_symbol=row["ticker_symbol"],
                    quantity=float(row["quantity"]),
                    cost_basis=float(row["cost_basis"]),
                    purchase_date=str(row["purchase_date"])
                    if row["purchase_date"]
                    else "",
                    notes=row["notes"] or "",
                )
                positions.append(pos)
                ticker_symbols.append(pos.ticker_symbol)

            price_map = {}
            if ticker_symbols:
                unique_tickers = list(set(ticker_symbols))

                async def fetch_price(ticker: str):
                    try:
                        info = await services.market_data.get_ticker_info_async(ticker)
                        if info and info.current_price:
                            return ticker, info.current_price
                    except Exception:
                        pass
                    return ticker, None

                # Use TaskGroup for structured concurrency
                async with asyncio.TaskGroup() as tg:
                    tasks = [
                        tg.create_task(fetch_price(t)) for t in unique_tickers
                    ]
                
                for task in tasks:
                    ticker, price = task.result()
                    if price is not None:
                        price_map[ticker] = price

            for pos in positions:
                current_price = price_map.get(pos.ticker_symbol, pos.cost_basis)
                pos.current_price = current_price
                pos.current_value = pos.quantity * current_price
                total_cost = pos.quantity * pos.cost_basis
                pos.gain_loss = pos.current_value - total_cost
                if total_cost > 0:
                    pos.gain_loss_percent = (pos.gain_loss / total_cost) * 100

                pos.fmt_quantity = f"{pos.quantity:,.2f}"
                pos.fmt_cost_basis = f"${pos.cost_basis:,.2f}"
                pos.fmt_current_price = f"${pos.current_price:,.2f}"
                pos.fmt_current_value = f"${pos.current_value:,.2f}"
                if pos.gain_loss >= 0:
                    pos.fmt_gain_loss = f"+${pos.gain_loss:,.2f}"
                else:
                    pos.fmt_gain_loss = f"-${abs(pos.gain_loss):,.2f}"
                sign = "+" if pos.gain_loss_percent >= 0 else ""
                pos.fmt_gain_loss_percent = f"{sign}{pos.gain_loss_percent:.1f}%"
                pos.gain_loss_color = (
                    "var(--green-11)" if pos.gain_loss >= 0 else "var(--red-11)"
                )
                pos.gain_loss_badge_color = "green" if pos.gain_loss >= 0 else "red"

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
            await run_sync(
                services.db.execute,
                """
                INSERT INTO portfolio (ticker_symbol, quantity, cost_basis, purchase_date, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ticker, quantity, cost_basis, purchase_date, self.form_notes.strip()),
            )

            # Clear form and reload positions
            self._clear_form()
            self.show_add_form = False
            await self.load_positions()

        except Exception as e:
            self.error_message = f"Error adding position: {str(e)}"

    async def delete_position(self, position_id: int):
        """Delete a position from the portfolio (internal, called after confirmation)."""
        try:
            await run_sync(
                services.db.execute,
                "DELETE FROM portfolio WHERE id = ?",
                (position_id,),
            )
            await self.load_positions()
        except Exception as e:
            self.error_message = f"Error deleting position: {str(e)}"
        finally:
            self.show_delete_confirm = False
            self.delete_confirm_position_id = 0
            self.delete_confirm_ticker = ""

    def confirm_delete_position(self, position_id: int):
        """Open delete confirmation dialog for a position."""
        for pos in self.positions:
            if pos.id == position_id:
                self.delete_confirm_ticker = pos.ticker_symbol
                break
        self.delete_confirm_position_id = position_id
        self.show_delete_confirm = True

    def cancel_delete(self):
        """Cancel delete confirmation."""
        self.show_delete_confirm = False
        self.delete_confirm_position_id = 0
        self.delete_confirm_ticker = ""

    async def execute_delete(self):
        """Execute the confirmed deletion."""
        if self.delete_confirm_position_id > 0:
            await self.delete_position(self.delete_confirm_position_id)

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

    @rx.var
    def top_gainers(self) -> list[dict]:
        """Top 3 positions by gain % (for daily brief)."""
        if not self.positions:
            return []
        sorted_pos = sorted(
            self.positions, key=lambda p: p.gain_loss_percent, reverse=True
        )
        return [
            {"symbol": p.ticker_symbol, "change_pct": p.gain_loss_percent}
            for p in sorted_pos[:3]
        ]

    @rx.var
    def top_losers(self) -> list[dict]:
        """Bottom 3 positions by gain % (for daily brief)."""
        if not self.positions:
            return []
        sorted_pos = sorted(self.positions, key=lambda p: p.gain_loss_percent)
        return [
            {"symbol": p.ticker_symbol, "change_pct": p.gain_loss_percent}
            for p in sorted_pos[:3]
        ]

    @rx.var
    def portfolio_summary_for_brief(self) -> dict:
        """Summary dict for daily brief prompt."""
        return {
            "total_value": self.total_value,
            "total_cost": self.total_cost,
            "total_pl": self.total_gain_loss,
            "total_pl_pct": self.total_gain_loss_percent,
            "position_count": len(self.positions),
            "top_gainers": self.top_gainers,
            "top_losers": self.top_losers,
        }
