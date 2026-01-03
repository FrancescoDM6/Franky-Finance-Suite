"""Phinan Finance Suite - Reflex Configuration."""

import os
import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

# Redis URL for production state management (avoids disk permission issues)
redis_url = os.environ.get("REDIS_URL")

config = rx.Config(
    app_name="phinan",
    api_url=os.environ.get("API_URL"),
    title="Phinan Finance Suite",
    description="Personal finance app with AI assistant",
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        SitemapPlugin(),
    ],
    # Use Redis for state management in production
    state_manager_mode="redis" if redis_url else "disk",
    redis_url=redis_url,
)