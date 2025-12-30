"""Root application state.

Keep minimal - only truly global state here.
Module-specific state should be in separate substates.
"""

import reflex as rx


class AppState(rx.State):
    """Root application state.

    Contains:
    - Navigation state
    - UI preferences (sidebar, assistant visibility)
    - User identification
    """

    # Navigation
    current_page: str = "home"

    # UI state
    sidebar_open: bool = True
    assistant_visible: bool = True

    # User (simple for now - can expand to multi-user later)
    user_id: str = "default_user"

    # Theme
    dark_mode: bool = False

    def toggle_sidebar(self):
        """Toggle sidebar visibility."""
        self.sidebar_open = not self.sidebar_open

    def toggle_assistant(self):
        """Toggle assistant panel visibility."""
        self.assistant_visible = not self.assistant_visible

    def set_page(self, page: str):
        """Set current page for navigation highlighting."""
        self.current_page = page

    def toggle_dark_mode(self):
        """Toggle dark mode."""
        self.dark_mode = not self.dark_mode

    @rx.var
    def theme_appearance(self) -> str:
        """Get theme appearance for Reflex."""
        return "dark" if self.dark_mode else "light"
