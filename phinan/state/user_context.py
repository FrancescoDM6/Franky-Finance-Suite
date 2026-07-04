"""Persistent user context state.

Loaded from DuckDB at session start, persisted on changes.
Contains user preferences, watchlist, and trading history.
"""

import json
import logging
from datetime import datetime

import reflex as rx

from ..core.async_utils import run_sync


logger = logging.getLogger(__name__)


_PERSISTED_FIELDS = {
    "active_profile": ("str", "active_profile"),
    "risk_tolerance": ("str", "risk_tolerance"),
    "typical_strategy": ("str", "typical_strategy"),
    "typical_timeframe": ("str", "typical_timeframe"),
    "default_range_period": ("str", "default_range_period"),
    "dark_mode": ("json_bool", "dark_mode"),
    "watchlist": ("json_list", "watchlist"),
    "avoid_list": ("json_list", "avoid_list"),
}


def _deserialize_context_value(value_type: str, value: str):
    """Deserialize a persisted context value according to its field type."""
    if value_type == "str":
        return value
    if value_type == "json_bool":
        return bool(json.loads(value))
    if value_type == "json_list":
        return json.loads(value)
    raise ValueError(f"Unsupported user context field type: {value_type}")


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
        from ..config.profiles import get_profile

        return get_profile(self.active_profile).name

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
            return

        from ..services import services

        try:
            # Query and field handling both derive from _PERSISTED_FIELDS, so
            # adding a persisted field is a single dict entry.
            keys = tuple(_PERSISTED_FIELDS)
            placeholders = ", ".join("?" for _ in keys)
            result = await run_sync(
                services.db.query,
                f"SELECT key, value FROM user_context WHERE key IN ({placeholders})",
                keys,
            )

            for row in result:
                key = row["key"]
                field_config = _PERSISTED_FIELDS.get(key)
                if field_config is None:
                    continue

                value_type, attribute = field_config
                # Decode each row independently so one malformed value does not
                # prevent the remaining preferences from loading.
                try:
                    value = _deserialize_context_value(value_type, row["value"])
                except (ValueError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "Skipping malformed user_context value for %s: %s", key, exc
                    )
                    continue
                setattr(self, attribute, value)

            self._loaded = True
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
        from ..config.profiles import get_profile

        profile_key = profile.lower()
        self.active_profile = profile_key

        # Apply profile-specific defaults (single source: config/profiles.py)
        defaults = get_profile(profile_key)
        self.risk_tolerance = defaults.risk_tolerance
        self.typical_strategy = defaults.typical_strategy
        self.typical_timeframe = defaults.typical_timeframe
        self.default_range_period = defaults.default_range_period

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

    def toggle_dark_mode(self):
        """Toggle dark mode preference."""
        self.dark_mode = not self.dark_mode
        self._save_context_value("dark_mode", json.dumps(self.dark_mode), "json")
