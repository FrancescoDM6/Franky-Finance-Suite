"""Modules for Phinan Finance Suite.

Each module is a self-contained tool the assistant can invoke.
Also accessible via direct UI for power users.
"""

from . import research, notes, options, portfolio

__all__ = ["research", "notes", "options", "portfolio"]
