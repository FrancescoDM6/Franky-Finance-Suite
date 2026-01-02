"""Phinan Finance Suite - Main Application Entry Point.

Personal finance app with AI assistant as the primary interface.
Modules (research, notes, options, portfolio) serve as tools the assistant can invoke.
"""

import reflex as rx

# Import pages to register them with Reflex
from .pages import index, settings
from .modules.research import page as research_page
from .modules.notes import page as notes_page
from .modules.options import page as options_page
from .modules.portfolio import page as portfolio_page

# Import states to register them
from .state.app import AppState
from .state.user_context import UserContextState
from .components.assistant.state import AssistantState

# Import API endpoints
from .api import health_api


def on_load():
    """Initialize services on first load."""
    from .services import services

    # Initialize database schema
    services.db.initialize_schema()


app = rx.App(
    theme=rx.theme(
        accent_color="blue",
        gray_color="slate",
        radius="medium",
    ),
    stylesheets=["/styles.css"],
    api_transformer=health_api,
)
