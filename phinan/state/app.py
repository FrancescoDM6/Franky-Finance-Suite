"""Root application state.

Keep minimal - only truly global state here.
Module-specific state should be in separate substates.
"""

import reflex as rx


class AppState(rx.State):
    """Root application state.

    Contains:
    - Navigation state
    - UI preferences (sidebar)
    - User identification
    """

    # Navigation
    current_page: str = "home"

    # UI state
    sidebar_open: bool = False

    # User (simple for now - can expand to multi-user later)
    user_id: str = "default_user"

    def toggle_sidebar(self):
        """Toggle sidebar visibility."""
        self.sidebar_open = not self.sidebar_open

    def set_page(self, page: str):
        """Set current page for navigation highlighting."""
        self.current_page = page
