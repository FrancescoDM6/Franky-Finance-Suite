"""Phinan Finance Suite - Main Application Entry Point.

Personal finance app with AI assistant as the primary interface.
Modules (research, notes, options, portfolio) serve as tools the assistant can invoke.
"""

# Performance: Install uvloop for 2-4x event loop improvement (Unix only)
# Must be done BEFORE importing asyncio or any async frameworks
import asyncio
import logging

logger = logging.getLogger(__name__)

try:
    import uvloop

    uvloop.install()

    # Log successful uvloop installation and performance boost
    logger.info(
        "uvloop successfully installed - Performance boost active (2-4x faster event loop)"
    )

    # Verify which event loop policy is active
    policy = asyncio.get_event_loop_policy()
    policy_type = type(policy).__name__
    logger.info(f"Event loop policy: {policy_type}")

    # Performance indicator for monitoring
    if hasattr(policy, "new_event_loop"):
        test_loop = policy.new_event_loop()
        if "uvloop" in str(type(test_loop)):
            logger.info(
                "PERFORMANCE: uvloop is active and ready for production workloads"
            )
        test_loop.close()

except ImportError:
    # uvloop not available (Windows) - use default asyncio event loop
    logger.info(
        "uvloop not available (Windows or not installed) - using default asyncio event loop"
    )
    logger.info(
        "PERFORMANCE: Running with standard asyncio (consider uvloop in Unix production)"
    )

except Exception as e:
    # Log any other errors during uvloop setup
    logger.error(f"uvloop installation failed: {e}")
    logger.info("PERFORMANCE: Falling back to default asyncio event loop")

import reflex as rx

# Import pages to register them with Reflex
from .pages import index, settings, ui_demo
from .modules.research import page as research_page
from .modules.notes import page as notes_page
from .modules.options import page as options_page
from .modules.portfolio import page as portfolio_page

# Import states to register them
from .state.app import AppState
from .state.user_context import UserContextState
# from .components.assistant.state import AssistantState

# Import API endpoints
from .api import health_api


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
