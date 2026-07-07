"""Options module workflow, packaged as a Reflex state mixin.

Handlers for the trade log (add/close/expire/edit/delete), the options
chain viewer, the single-leg strategy preview, and the LLM pattern
analysis. Mixed into OptionsTradingState (see state.py).
"""

import logging
from datetime import datetime

import reflex as rx

from ...core.async_utils import run_sync
from ...services.options_analytics import preview_strategy
from ..research import options_logic
from ..research.research_cache import LRUCache
from ..research.ticker_index import ticker_index
from . import form_logic, persistence, trade_logic

logger = logging.getLogger(__name__)

# Chain cache for the trading view (own instance; research has its own)
_chain_cache = LRUCache()


def _trade_label(trade: dict) -> str:
    """Compact label like 'AAPL $185C 07/17'."""
    exp = trade.get("expiration_date") or ""
    try:
        exp_short = datetime.fromisoformat(exp[:10]).strftime("%m/%d")
    except ValueError:
        exp_short = exp
    letter = "C" if trade.get("option_type") == "call" else "P"
    return f"{trade.get('ticker_symbol', '?')} ${trade.get('strike_price', 0):g}{letter} {exp_short}"


def _decorate_trade(trade: dict) -> dict:
    """Bake display fields into a trade row (portfolio fmt_ pattern)."""
    trade = dict(trade)
    trade["label"] = _trade_label(trade)
    trade["strategy_label"] = trade_logic.STRATEGY_LABELS.get(
        trade.get("strategy", ""), trade.get("strategy", "")
    )
    trade["fmt_premium"] = f"${trade.get('premium', 0):.2f}"
    exit_price = trade.get("exit_price")
    trade["fmt_exit"] = f"${exit_price:.2f}" if exit_price is not None else "-"

    pnl = trade.get("realized_pnl")
    if pnl is None:
        trade["fmt_pnl"] = "-"
        trade["pnl_color"] = "var(--gray-11)"
    else:
        sign = "+" if pnl >= 0 else "-"
        trade["fmt_pnl"] = f"{sign}${abs(pnl):,.2f}"
        trade["pnl_color"] = "var(--green-11)" if pnl >= 0 else "var(--red-11)"

    status = trade.get("status", "open")
    trade["status_badge_color"] = {
        "open": "blue",
        "closed": "green" if (pnl or 0) >= 0 else "red",
        "expired": "gray",
    }.get(status, "gray")

    trade["dte"] = options_logic.days_to_expiry(
        (trade.get("expiration_date") or "")[:10]
    )
    if trade.get("opened_at") and trade.get("closed_at"):
        try:
            trade["held_days"] = trade_logic.holding_days(
                datetime.fromisoformat(trade["opened_at"]),
                datetime.fromisoformat(trade["closed_at"]),
            )
        except ValueError:
            trade["held_days"] = 0
    else:
        trade["held_days"] = 0
    trade["opened_short"] = (trade.get("opened_at") or "")[:10]
    return trade


class OptionsWorkflowMixin(rx.State, mixin=True):
    """Async orchestration event handlers for the Options module."""

    # ------------------------------------------------------------------
    # Page load + trades
    # ------------------------------------------------------------------

    async def load_page(self):
        """On-load: shared ticker index + trades + performance."""
        ticker_index.ensure_loaded()
        await self._reload_trades()

    async def _reload_trades(self):
        from ...services import services

        self.is_loading_trades = True
        try:
            open_rows = await run_sync(persistence.list_trades, services.db, "open")
            closed_rows = await run_sync(
                persistence.list_trades, services.db, "closed_or_expired"
            )
            self.open_trades = [_decorate_trade(t) for t in open_rows]
            self.closed_trades = [_decorate_trade(t) for t in closed_rows]
            self.performance = trade_logic.compute_performance(closed_rows)
            self.trades_error = ""
        except Exception as e:
            logger.error("Error loading options trades: %s", e)
            self.trades_error = f"Could not load trades: {e}"
        finally:
            self.is_loading_trades = False

    async def log_trade(self):
        """Validate the trade form and insert (or update when editing)."""
        from ...services import services

        try:
            trade = form_logic.validate_trade_form(self._trade_form_fields())
        except form_logic.FormValidationError as e:
            self.form_error = str(e)
            return

        self.form_error = ""
        try:
            if self.editing_trade_id > 0:
                await run_sync(
                    persistence.update_trade,
                    services.db,
                    self.editing_trade_id,
                    trade,
                )
                message = f"Updated {trade['ticker_symbol']} trade"
                self.editing_trade_id = 0
            else:
                await run_sync(persistence.add_trade, services.db, trade)
                message = f"Logged {trade['ticker_symbol']} {trade['strategy']}"
            await self._reload_trades()
            self._clear_trade_form()
            return rx.toast.success(message)
        except Exception as e:
            logger.error("Error saving trade: %s", e)
            self.form_error = f"Could not save trade: {e}"

    def edit_trade(self, trade_id: int):
        """Load an open trade back into the form for editing."""
        trade = next((t for t in self.open_trades if t["id"] == trade_id), None)
        if trade is None:
            return
        self.editing_trade_id = trade_id
        self.form_ticker = trade["ticker_symbol"]
        self.form_option_type = trade["option_type"]
        self.form_position_type = trade["position_type"]
        self.form_strategy = trade["strategy"]
        self.form_strike = f"{trade['strike_price']:g}"
        self.form_premium = f"{trade['premium']:g}"
        self.form_quantity = str(trade["quantity"])
        self.form_expiration = trade["expiration_date"][:10]
        self.form_opened_date = trade["opened_at"][:10]
        self.form_notes = trade["notes"]
        self.form_error = ""
        self._recompute_preview()

    def cancel_edit(self):
        """Abandon an in-progress trade edit."""
        self.editing_trade_id = 0
        self._clear_trade_form()

    # -- close / expire flow -------------------------------------------

    def open_close_dialog(self, trade_id: int, expire: bool):
        trade = next((t for t in self.open_trades if t["id"] == trade_id), None)
        if trade is None:
            return
        self.close_trade_id = trade_id
        self.close_trade_label = trade["label"]
        self.close_is_expire = expire
        self.close_exit_price = "0" if expire else ""
        self.close_error = ""
        self.show_close_dialog = True

    def cancel_close(self):
        self.show_close_dialog = False
        self.close_trade_id = 0
        self.close_exit_price = ""
        self.close_error = ""

    async def confirm_close(self):
        from ...services import services

        trade = next(
            (t for t in self.open_trades if t["id"] == self.close_trade_id), None
        )
        if trade is None:
            self.show_close_dialog = False
            return

        try:
            exit_price = (
                0.0
                if self.close_is_expire
                else form_logic.validate_close_form(self.close_exit_price)
            )
        except form_logic.FormValidationError as e:
            self.close_error = str(e)
            return

        pnl = trade_logic.compute_realized_pnl(
            trade["position_type"], trade["premium"], exit_price, trade["quantity"]
        )
        status = "expired" if self.close_is_expire else "closed"

        try:
            await run_sync(
                persistence.close_trade,
                services.db,
                self.close_trade_id,
                exit_price,
                pnl,
                status,
            )
        except Exception as e:
            logger.error("Error closing trade %s: %s", self.close_trade_id, e)
            self.close_error = f"Could not close trade: {e}"
            return

        self.show_close_dialog = False
        self.close_trade_id = 0
        self.close_exit_price = ""
        await self._reload_trades()
        sign = "+" if pnl >= 0 else "-"
        return rx.toast.success(
            f"{trade['label']} {status}: {sign}${abs(pnl):,.2f}"
        )

    # -- delete flow (portfolio confirm pattern) ------------------------

    def confirm_delete(self, trade_id: int):
        trade = next(
            (t for t in self.open_trades + self.closed_trades if t["id"] == trade_id),
            None,
        )
        if trade is None:
            return
        self.delete_confirm_id = trade_id
        self.delete_confirm_label = trade["label"]
        self.show_delete_confirm = True

    def cancel_delete(self):
        self.show_delete_confirm = False
        self.delete_confirm_id = 0

    async def execute_delete(self):
        from ...services import services

        if self.delete_confirm_id <= 0:
            return
        label = self.delete_confirm_label
        try:
            await run_sync(persistence.delete_trade, services.db, self.delete_confirm_id)
        except Exception as e:
            logger.error("Error deleting trade: %s", e)
            self.trades_error = f"Could not delete trade: {e}"
            return
        finally:
            self.show_delete_confirm = False
            self.delete_confirm_id = 0
        await self._reload_trades()
        return rx.toast.success(f"Deleted {label}")

    # ------------------------------------------------------------------
    # Chain viewer
    # ------------------------------------------------------------------

    def set_chain_ticker_input(self, value: str):
        self.form_chain_ticker = value.upper()
        self.show_autocomplete = len(value.strip()) >= 1
        self.chain_error = ""

    def select_ticker_suggestion(self, option: str):
        self.form_chain_ticker = option.split(" - ")[0] if " - " in option else option
        self.show_autocomplete = False

    async def load_chain_for_ticker(self):
        """Commit the ticker input and load expirations + default chain."""
        from ...services import services
        from ...state.user_context import UserContextState

        ticker = self.form_chain_ticker.strip().upper()
        ticker = ticker.split(" - ")[0] if " - " in ticker else ticker
        if not ticker:
            self.chain_error = "Enter a ticker"
            return

        self.show_autocomplete = False
        self.chain_loading = True
        self.chain_error = ""
        yield

        try:
            info = await services.market_data.get_ticker_info_async(ticker)
            if info is None or not info.current_price:
                self.chain_error = f"Could not find ticker {ticker}"
                return
            self.chain_ticker = ticker
            self.chain_spot = float(info.current_price)

            expirations = await services.market_data.get_options_expirations_async(
                ticker
            )
            if not expirations:
                self.chain_expirations = []
                self.chain_expiration = ""
                self.chain_calls = []
                self.chain_puts = []
                self.chain_error = "No options listed for this ticker"
                return

            self.chain_expirations = expirations
            user_ctx = await self.get_state(UserContextState)
            self.chain_expiration = options_logic.select_default_expiration(
                expirations, user_ctx.typical_timeframe
            )
            yield

            await self._load_expiration()

        except Exception as e:
            logger.error("Error loading chain for %s: %s", ticker, e)
            self.chain_error = f"Error loading chain: {e}"
        finally:
            self.chain_loading = False

    async def set_chain_expiration(self, expiration: str):
        self.chain_expiration = expiration
        self.chain_loading = True
        yield
        try:
            await self._load_expiration()
        finally:
            self.chain_loading = False

    async def _load_expiration(self):
        from ...services import services

        if not self.chain_ticker or not self.chain_expiration:
            return

        self.chain_days_to_expiry = options_logic.days_to_expiry(self.chain_expiration)

        cache_key = f"{self.chain_ticker}:{self.chain_expiration}"
        chain = _chain_cache.get(cache_key)
        if chain is None:
            chain = await services.market_data.get_options_chain_async(
                self.chain_ticker, self.chain_expiration
            )
            _chain_cache.set(cache_key, chain)

        calls_df = chain.get("calls")
        puts_df = chain.get("puts")
        if calls_df is None or calls_df.empty:
            self.chain_calls = []
            self.chain_puts = []
            self.chain_error = "No chain data for this expiration"
            return

        strikes = sorted(calls_df["strike"].unique().tolist())
        window = options_logic.strikes_around_atm(strikes, self.chain_spot)
        strike_info = {s["strike"]: s for s in window}
        selected = list(strike_info.keys())

        self.chain_calls = options_logic.format_chain_rows(
            calls_df, selected, strike_info, "call"
        )
        self.chain_puts = options_logic.format_chain_rows(
            puts_df, selected, strike_info, "put"
        )
        self.chain_error = ""

    def select_chain_row(self, row: dict, option_type: str):
        """Prefill the trade form from a clicked chain row."""
        self.form_ticker = self.chain_ticker
        self.form_option_type = option_type
        self.form_strike = f"{row.get('strike', 0):g}"
        self.form_premium = f"{row.get('mid', 0):g}"
        self.form_iv = f"{row.get('iv', 0) * 100:.1f}"
        self.form_expiration = self.chain_expiration
        self.form_strategy = form_logic.derive_strategy(
            option_type, self.form_position_type
        )
        self.form_error = ""
        self._recompute_preview()

    # ------------------------------------------------------------------
    # Strategy preview (pure math, recomputed on form edits)
    # ------------------------------------------------------------------

    def set_form_field(self, field: str, value: str):
        """Generic trade-form setter; keeps strategy consistent."""
        attr = f"form_{field}"
        if not hasattr(self, attr):
            logger.warning("Unknown options form field: %s", field)
            return
        setattr(self, attr, value)
        if field in ("option_type", "position_type"):
            self.form_strategy = form_logic.derive_strategy(
                self.form_option_type, self.form_position_type
            )
        self.form_error = ""
        self._recompute_preview()

    def set_close_price_input(self, value: str):
        self.close_exit_price = value
        self.close_error = ""

    def _recompute_preview(self):
        from ...config.settings import settings

        self.preview_error = ""
        try:
            strike = float(self.form_strike)
            premium = float(self.form_premium)
            contracts = int(self.form_quantity or "1")
            if strike <= 0 or premium <= 0 or contracts < 1:
                self.preview = {}
                return
        except ValueError:
            self.preview = {}
            return

        spot = self.chain_spot if self.chain_ticker == self.form_ticker else 0.0
        if spot <= 0:
            # No spot available (manual entry without chain): center on strike
            spot = strike

        try:
            sigma = float(self.form_iv) / 100.0 if self.form_iv.strip() else 0.0
        except ValueError:
            sigma = 0.0

        t_years = max(
            options_logic.days_to_expiry(self.form_expiration) / 365.0, 0.0
        )

        try:
            self.preview = preview_strategy(
                spot=spot,
                strike=strike,
                premium=premium,
                option_type=self.form_option_type,
                position_type=self.form_position_type,
                contracts=contracts,
                sigma=sigma,
                r=settings.structured_products.risk_free_rate,
                t_years=t_years,
            )
        except Exception as e:
            logger.warning("Preview computation failed: %s", e)
            self.preview = {}
            self.preview_error = f"Preview unavailable: {e}"

    # ------------------------------------------------------------------
    # LLM pattern analysis
    # ------------------------------------------------------------------

    async def analyze_patterns(self):
        """Generate the LLM read on the user's closed-trade history."""
        from ...config.profiles import get_profile
        from ...services import services
        from ...state.user_context import UserContextState
        from . import prompts

        self._pattern_generation += 1
        generation = self._pattern_generation
        self.is_analyzing_patterns = True
        self.pattern_error = ""
        yield

        try:
            healthy = await run_sync(services.synthesis.health_check)
            if not healthy:
                self.pattern_error = "AI analysis unavailable: service offline"
                return

            user_ctx = await self.get_state(UserContextState)
            profile = get_profile(user_ctx.active_profile)
            prompt = prompts.build_pattern_prompt(
                self.performance,
                trade_logic.format_trades_for_prompt(self.closed_trades),
                profile.name,
                profile.description,
            )
            result = await run_sync(services.synthesis.generate_from_prompt, prompt)

            if generation != self._pattern_generation:
                return
            if result.success and result.content:
                self.pattern_analysis = result.content
            else:
                self.pattern_error = "AI analysis failed: please try again"
        except Exception as e:
            logger.warning("Pattern analysis failed: %s", e)
            if generation == self._pattern_generation:
                self.pattern_error = "AI analysis failed: please try again"
        finally:
            if generation == self._pattern_generation:
                self.is_analyzing_patterns = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trade_form_fields(self) -> dict:
        return {
            "ticker": self.form_ticker,
            "option_type": self.form_option_type,
            "position_type": self.form_position_type,
            "strategy": self.form_strategy,
            "strike": self.form_strike,
            "premium": self.form_premium,
            "quantity": self.form_quantity,
            "expiration_date": self.form_expiration,
            "opened_date": self.form_opened_date,
            "notes": self.form_notes,
        }

    def _clear_trade_form(self):
        self.form_ticker = ""
        self.form_strike = ""
        self.form_premium = ""
        self.form_quantity = "1"
        self.form_expiration = ""
        self.form_opened_date = ""
        self.form_notes = ""
        self.form_iv = ""
        self.preview = {}
        self.preview_error = ""
