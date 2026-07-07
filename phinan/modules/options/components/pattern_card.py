"""LLM trade-pattern analysis card for the Options module."""

import reflex as rx

from ....components.ui import synthesis_card
from ..state import OptionsTradingState


def pattern_card() -> rx.Component:
    """Phin's read on what is working and what is losing money."""
    return synthesis_card(
        rx.vstack(
            rx.hstack(
                rx.icon("sparkles", size=18, color="var(--purple-9)"),
                rx.heading("Pattern Analysis", size="4"),
                rx.spacer(),
                rx.button(
                    rx.icon("scan-search", size=14),
                    "Analyze my trading",
                    on_click=OptionsTradingState.analyze_patterns,
                    loading=OptionsTradingState.is_analyzing_patterns,
                    disabled=~OptionsTradingState.can_analyze_patterns,
                    size="1",
                    variant="soft",
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            rx.cond(
                OptionsTradingState.pattern_analysis != "",
                rx.vstack(
                    rx.markdown(OptionsTradingState.pattern_analysis),
                    rx.text(
                        "Generated from your closed-trade metrics above; the "
                        "AI identifies patterns, it does not recompute numbers.",
                        size="1",
                        color="var(--pfs-text-muted)",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.cond(
                    OptionsTradingState.pattern_error != "",
                    rx.callout(
                        OptionsTradingState.pattern_error,
                        icon="circle-alert",
                        color_scheme="amber",
                        size="1",
                        width="100%",
                    ),
                    rx.text(
                        rx.cond(
                            OptionsTradingState.can_analyze_patterns,
                            "Ask Phin to look for patterns across your closed trades.",
                            "Close at least 5 trades to unlock pattern analysis.",
                        ),
                        size="2",
                        color="var(--pfs-text-muted)",
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
