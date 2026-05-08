"""Persistent user context state.

Loaded from DuckDB at session start, persisted on changes.
Contains user preferences, watchlist, and trading history.
"""

import json
import logging
from datetime import datetime

import reflex as rx
from reflex.style import set_color_mode

from ..core.async_utils import run_sync


logger = logging.getLogger(__name__)


class UserContextState(rx.State):
    """User context state - persistent across sessions.

    This state maintains:
    - Trading preferences (risk tolerance, strategy type)
    - Watchlist
    - Active user profile (Conservative/Aggressive/Standard modes)
    """

    # Profile selection
    active_profile: str = "standard"

    # Trading preferences
    risk_tolerance: str = "conservative"  # "conservative" or "aggressive"
    typical_strategy: str = "entry_exit"  # "entry_exit" or "directional"
    typical_timeframe: str = "2_weeks"  # "1_week", "2_weeks", "1_2_months", or "varies"
    default_range_period: str = "3mo"  # "1mo", "3mo", "6mo", "1y"
    dark_mode: bool = False

    # Watchlist
    watchlist: list[str] = []

    # Avoid list (stocks to not suggest)
    avoid_list: list[str] = []

    # Notes/preferences
    preferences: list[str] = []

    # Loading state
    _loaded: bool = False

    @rx.var
    def watchlist_count(self) -> int:
        """Number of stocks in watchlist."""
        return len(self.watchlist)

    @rx.var
    def profile_display_name(self) -> str:
        """Display name for current profile."""
        names = {"conservative": "Conservative", "aggressive": "Aggressive", "standard": "Standard"}
        return names.get(self.active_profile, "Standard")

    @rx.var
    def timeframe_display_name(self) -> str:
        """Display name for current trading timeframe."""
        names = {
            "1_week": "1 week",
            "2_weeks": "2 weeks",
            "1_2_months": "1-2 months",
            "varies": "Varies",
        }
        return names.get(self.typical_timeframe, "2 weeks")

    async def load_context(self):
        """Load user context from database.

        DB I/O is dispatched through run_sync so the asyncio event loop is
        not blocked while DuckDB serializes access. Blocking here prevented
        the websocket from completing its initial state delta when multiple
        clients connected, which surfaced as a stuck "Connecting" overlay.
        """
        if self._loaded:
            yield set_color_mode("dark" if self.dark_mode else "light")
            return

        from ..services import services

        try:
            result = await run_sync(
                services.db.query,
                "SELECT key, value FROM user_context WHERE key IN (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "active_profile",
                    "risk_tolerance",
                    "typical_strategy",
                    "typical_timeframe",
                    "default_range_period",
                    "dark_mode",
                    "watchlist",
                    "avoid_list",
                ),
            )

            for row in result:
                key = row["key"]
                value = row["value"]

                if key == "active_profile":
                    self.active_profile = value
                elif key == "risk_tolerance":
                    self.risk_tolerance = value
                elif key == "typical_strategy":
                    self.typical_strategy = value
                elif key == "typical_timeframe":
                    self.typical_timeframe = value
                elif key == "default_range_period":
                    self.default_range_period = value
                elif key == "dark_mode":
                    self.dark_mode = bool(json.loads(value))
                elif key == "watchlist":
                    self.watchlist = json.loads(value)
                elif key == "avoid_list":
                    self.avoid_list = json.loads(value)

            self._loaded = True
            yield set_color_mode("dark" if self.dark_mode else "light")
        except Exception as e:
            logger.error("Error loading user context: %s", e)

    def _save_context_value(self, key: str, value: str, value_type: str = "string"):
        """Save a single context value to database."""
        from ..services import services

        try:
            services.db.execute(
                """
                INSERT INTO user_context (key, value, value_type, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, value_type, datetime.now()),
            )
        except Exception as e:
            logger.error("Error saving context value %s: %s", key, e)

    def set_profile(self, profile: str):
        """Switch user profile and apply defaults."""
        profile_key = profile.lower()
        self.active_profile = profile_key

        # Apply profile-specific defaults
        profile_defaults = {
            "conservative": {
                "risk_tolerance": "conservative",
                "typical_strategy": "entry_exit",
                "typical_timeframe": "2_weeks",
                "default_range_period": "3mo",
            },
            "aggressive": {
                "risk_tolerance": "aggressive",
                "typical_strategy": "directional",
                "typical_timeframe": "1_2_months",
                "default_range_period": "6mo",
            },
            "standard": {
                "risk_tolerance": "learning",
                "typical_strategy": "varies",
                "typical_timeframe": "varies",
                "default_range_period": "6mo",
            },
        }

        if profile_key in profile_defaults:
            defaults = profile_defaults[profile_key]
            self.risk_tolerance = defaults["risk_tolerance"]
            self.typical_strategy = defaults["typical_strategy"]
            self.typical_timeframe = defaults["typical_timeframe"]
            self.default_range_period = defaults["default_range_period"]

        self._save_context_value("active_profile", self.active_profile)
        self._save_context_value("risk_tolerance", self.risk_tolerance)
        self._save_context_value("typical_strategy", self.typical_strategy)
        self._save_context_value("typical_timeframe", self.typical_timeframe)
        self._save_context_value("default_range_period", self.default_range_period)

    def add_to_watchlist(self, symbol: str):
        """Add symbol to watchlist."""
        symbol = symbol.upper().strip()
        if symbol and symbol not in self.watchlist:
            self.watchlist = self.watchlist + [symbol]
            import json

            self._save_context_value("watchlist", json.dumps(self.watchlist), "json")

    def remove_from_watchlist(self, symbol: str):
        """Remove symbol from watchlist."""
        symbol = symbol.upper().strip()
        if symbol in self.watchlist:
            self.watchlist = [s for s in self.watchlist if s != symbol]
            import json

            self._save_context_value("watchlist", json.dumps(self.watchlist), "json")

    def add_to_avoid_list(self, symbol: str):
        """Add symbol to avoid list."""
        symbol = symbol.upper().strip()
        if symbol and symbol not in self.avoid_list:
            self.avoid_list = self.avoid_list + [symbol]
            import json

            self._save_context_value("avoid_list", json.dumps(self.avoid_list), "json")

    def remove_from_avoid_list(self, symbol: str):
        """Remove symbol from avoid list."""
        symbol = symbol.upper().strip()
        if symbol in self.avoid_list:
            self.avoid_list = [s for s in self.avoid_list if s != symbol]
            import json

            self._save_context_value("avoid_list", json.dumps(self.avoid_list), "json")

    def set_typical_timeframe(self, value: str):
        """Set default trading timeframe."""
        self.typical_timeframe = value
        self._save_context_value("typical_timeframe", value)

    def set_range_period(self, period: str):
        """Set default range period."""
        self.default_range_period = period
        self._save_context_value("default_range_period", period)

    def set_dark_mode(self, value: bool):
        """Set dark mode preference."""
        self.dark_mode = value
        self._save_context_value("dark_mode", json.dumps(self.dark_mode), "json")
        return set_color_mode("dark" if self.dark_mode else "light")

    def toggle_dark_mode(self):
        """Toggle dark mode preference."""
        self.dark_mode = not self.dark_mode
        self._save_context_value("dark_mode", json.dumps(self.dark_mode), "json")
        return set_color_mode("dark" if self.dark_mode else "light")
