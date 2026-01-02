"""API module for Phinan Finance Suite.

Contains FastAPI endpoints that extend the Reflex application.
"""

from .health import health_api

__all__ = ["health_api"]
