"""Phinan Finance Suite - Main Application Entry Point.

Personal finance app with AI assistant as the primary interface.
Modules (research, notes, options, portfolio) serve as tools the assistant can invoke.
"""

import logging

# Configure basic logging so warnings/infos show up in the reflex console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# NOTE: do NOT call uvloop.install() here.
# Granian (the production server) forks its workers from this parent
# process. Installing uvloop at module level allocates libuv state and
# sets a global event-loop policy, both of which are inherited across
# fork and cause the worker child to SIGSEGV on startup. Granian on
# Linux uses its own Rust event loop (rloop) by default, which is
# already as fast as uvloop, so there is no performance benefit to
# installing uvloop in the parent.

import reflex as rx  # noqa: E402

# Import pages to register them with Reflex
from .pages import index, settings  # noqa: F401, E402
from .modules.research import page as research_page  # noqa: F401, E402
from .modules.notes import page as notes_page  # noqa: F401, E402
from .modules.options import page as options_page  # noqa: F401, E402
from .modules.portfolio import page as portfolio_page  # noqa: F401, E402

# Import states to register them
from .state.app import AppState  # noqa: F401, E402
from .state.user_context import UserContextState  # noqa: F401, E402

# Import API endpoints
from .api import health_api  # noqa: E402


def on_load():
    """Initialize services on first load."""
    from .services import services

    # Initialize database schema
    services.db.initialize_schema()


app = rx.App(
    theme=rx.theme(
        accent_color="teal",
        gray_color="sand",
        radius="large",
    ),
    stylesheets=["/styles.css"],
    api_transformer=health_api,
)
