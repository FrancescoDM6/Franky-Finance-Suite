"""Phinan Finance Suite - Reflex Configuration."""

import reflex as rx

config = rx.Config(
    app_name="phinan",
    title="Phinan Finance Suite",
    description="Personal finance app with AI assistant",
    plugins=[
        rx.plugins.TailwindV4Plugin(),
    ],
)