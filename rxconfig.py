"""Phinan Finance Suite - Reflex Configuration."""

import os
import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="phinan",
    api_url=os.environ.get("API_URL"),
    title="Phinan Finance Suite",
    description="Personal finance app with AI assistant",
    plugins=[
        rx.plugins.TailwindV4Plugin(),
        SitemapPlugin(),
    ],
)