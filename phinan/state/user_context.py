"""Persistent user context state.

Loaded from DuckDB at session start, persisted on changes.
Contains user preferences, watchlist, and trading history.
"""

import reflex as rx
from datetime import datetime
from typing import Optional


class UserContextState(rx.State):
    """User context state - persistent across sessions.

    This state maintains:
    - Trading preferences (risk tolerance, strategy type)
    - Watchlist
    - Active user profile (Papi/Tio/Franky modes)
    """

    # Profile selection
    active_profile: str = "franky"

    # Trading preferences
    risk_tolerance: str = "conservative"  # "conservative" or "aggressive"
    typical_strategy: str = "entry_exit"  # "entry_exit" or "directional"
    typical_timeframe: str = "2_weeks"  # "2_weeks" or "1_2_months"
    default_range_period: str = "3mo"  # "1mo", "3mo", "6mo", "1y"

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
        names = {"papi": "Papi", "tio": "Tio", "franky": "Franky"}
        return names.get(self.active_profile, "Franky")

    async def load_context(self):
        """Load user context from database."""
        if self._loaded:
            return

        from ..services import services

        try:
            result = services.db.query(
                "SELECT key, value FROM user_context WHERE key IN (?, ?, ?, ?, ?, ?)",
                (
                    "active_profile",
                    "risk_tolerance",
                    "typical_strategy",
                    "typical_timeframe",
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
                elif key == "watchlist":
                    import json
                    self.watchlist = json.loads(value)
                elif key == "avoid_list":
                    import json
                    self.avoid_list = json.loads(value)

            self._loaded = True
        except Exception as e:
            print(f"Error loading user context: {e}")

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
            print(f"Error saving context value: {e}")

    def set_profile(self, profile: str):
        """Switch user profile and apply defaults."""
        self.active_profile = profile.lower()

        # Apply profile-specific defaults
        profile_defaults = {
            "papi": {
                "risk_tolerance": "conservative",
                "typical_strategy": "entry_exit",
                "typical_timeframe": "2_weeks",
                "default_range_period": "3mo",
            },
            "tio": {
                "risk_tolerance": "aggressive",
                "typical_strategy": "directional",
                "typical_timeframe": "1_2_months",
                "default_range_period": "6mo",
            },
            "franky": {
                "risk_tolerance": "learning",
                "typical_strategy": "varies",
                "typical_timeframe": "varies",
                "default_range_period": "6mo",
            },
        }

        if profile in profile_defaults:
            defaults = profile_defaults[profile]
            self.risk_tolerance = defaults["risk_tolerance"]
            self.typical_strategy = defaults["typical_strategy"]
            self.typical_timeframe = defaults["typical_timeframe"]
            self.default_range_period = defaults["default_range_period"]

        self._save_context_value("active_profile", self.active_profile)

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

    def set_range_period(self, period: str):
        """Set default range period."""
        self.default_range_period = period
        self._save_context_value("default_range_period", period)
