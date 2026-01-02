"""Analyst data card component."""

import reflex as rx
from ..state import ResearchState


def rating_distribution_bar(label: str, count_var, color: str, total_var) -> rx.Component:
    """Single rating distribution bar."""
    return rx.hstack(
        rx.text(label, size="1", width="80px"),
        rx.box(
            rx.progress(
                value=rx.cond(
                    total_var > 0,
                    (count_var * 100 / total_var).to(int),
                    0,
                ),
                width="100%",
                height="8px",
                color_scheme=color,
            ),
            flex="1",
        ),
        rx.text(count_var, size="1", width="24px", text_align="right"),
        spacing="2",
        width="100%",
        align="center",
    )


def rating_distribution() -> rx.Component:
    """Rating distribution bars."""
    total = ResearchState.total_analyst_recommendations

    return rx.cond(
        total > 0,
        rx.vstack(
            rx.text("Rating Distribution", size="1", color_scheme="gray", weight="medium"),
            rating_distribution_bar("Strong Buy", ResearchState.rec_strong_buy, "green", total),
            rating_distribution_bar("Buy", ResearchState.rec_buy, "grass", total),
            rating_distribution_bar("Hold", ResearchState.rec_hold, "gray", total),
            rating_distribution_bar("Sell", ResearchState.rec_sell, "orange", total),
            rating_distribution_bar("Strong Sell", ResearchState.rec_strong_sell, "red", total),
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def price_targets_row() -> rx.Component:
    """Price target spread display."""
    return rx.cond(
        ResearchState.target_mean > 0,
        rx.vstack(
            rx.text("Price Targets", size="1", color_scheme="gray", weight="medium"),
            rx.hstack(
                rx.vstack(
                    rx.text("Low", size="1", color_scheme="gray"),
                    rx.text(
                        "$", ResearchState.target_low,
                        size="2",
                        color="var(--red-11)",
                    ),
                    align="center",
                    spacing="0",
                ),
                rx.vstack(
                    rx.text("Mean", size="1", color_scheme="gray"),
                    rx.text(
                        "$", ResearchState.target_mean,
                        size="2",
                        weight="bold",
                    ),
                    align="center",
                    spacing="0",
                ),
                rx.vstack(
                    rx.text("High", size="1", color_scheme="gray"),
                    rx.text(
                        "$", ResearchState.target_high,
                        size="2",
                        color="var(--green-11)",
                    ),
                    align="center",
                    spacing="0",
                ),
                justify="between",
                width="100%",
            ),
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def recent_changes_list() -> rx.Component:
    """Recent analyst rating changes."""
    return rx.cond(
        ResearchState.recent_analyst_changes.length() > 0,
        rx.vstack(
            rx.text("Recent Changes", size="1", color_scheme="gray", weight="medium"),
            rx.foreach(
                ResearchState.recent_analyst_changes,
                lambda change: rx.hstack(
                    rx.text(change["date"], size="1", color_scheme="gray", width="50px"),
                    rx.text(change["firm"], size="1", weight="medium", flex="1"),
                    rx.badge(
                        change["to_grade"],
                        size="1",
                        color_scheme=rx.cond(
                            change["to_grade"].to(str).contains("Buy"),
                            "green",
                            rx.cond(
                                change["to_grade"].to(str).contains("Sell"),
                                "red",
                                "gray",
                            ),
                        ),
                    ),
                    spacing="2",
                    width="100%",
                    align="center",
                ),
            ),
            spacing="1",
            width="100%",
        ),
        rx.fragment(),
    )


def analyst_card() -> rx.Component:
    """Analyst consensus card with detailed breakdown."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Analyst Consensus", size="4"),
                rx.spacer(),
                rx.cond(
                    ResearchState.analyst_data.get("num_analysts"),
                    rx.badge(
                        ResearchState.analyst_data.get("num_analysts"),
                        " Analysts",
                        variant="soft",
                    ),
                    rx.fragment(),
                ),
                width="100%",
                align="center",
            ),
            rx.divider(),
            # Summary row
            rx.hstack(
                rx.vstack(
                    rx.text("Rating", size="1", color_scheme="gray"),
                    rx.badge(
                        rx.cond(
                            ResearchState.analyst_data.get("rating"),
                            ResearchState.analyst_data.get("rating"),
                            "N/A",
                        ),
                        color_scheme=rx.cond(
                            ResearchState.analyst_data.get("rating") == "buy",
                            "green",
                            rx.cond(
                                ResearchState.analyst_data.get("rating") == "sell",
                                "red",
                                "gray",
                            ),
                        ),
                        size="2",
                    ),
                    align="center",
                ),
                rx.vstack(
                    rx.text("Target Price", size="1", color_scheme="gray"),
                    rx.text(
                        rx.cond(
                            ResearchState.analyst_data.get("target_price"),
                            rx.text("$", ResearchState.analyst_data.get("target_price")),
                            "N/A",
                        ),
                        size="3",
                        weight="bold",
                    ),
                    rx.cond(
                        ResearchState.analyst_data.get("target_price") & ResearchState.current_price,
                        rx.badge(
                            rx.text(
                                ResearchState.upside_percentage,
                                "% Upside",
                            ),
                            color_scheme=rx.cond(
                                ResearchState.upside_percentage > 0,
                                "green",
                                "red",
                            ),
                            variant="soft",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    align="center",
                ),
                justify="between",
                width="100%",
            ),
            rx.divider(),
            # Rating distribution
            rating_distribution(),
            # Price targets
            price_targets_row(),
            # Recent changes
            recent_changes_list(),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
