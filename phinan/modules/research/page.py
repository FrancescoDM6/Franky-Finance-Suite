"""Research page - Company research for options trading."""

import reflex as rx

from ...components.layout import main_layout
from ...state.app import AppState
from ...state.user_context import UserContextState
from .state import ResearchState
from .components import quality_card, analyst_card, range_card, news_card, chart_card


def research_header() -> rx.Component:
    """Research page header with input and controls."""
    return rx.hstack(
        rx.input(
            placeholder="Enter ticker (e.g., AAPL)",
            value=ResearchState.ticker_input,
            on_change=ResearchState.set_ticker_input,
            size="2",
            width="200px",
        ),
        rx.button(
            rx.icon("search", size=16),
            "Research",
            on_click=ResearchState.research_ticker,
            loading=ResearchState.is_loading,
            color_scheme="blue",
            size="2",
        ),
        rx.button(
            "Clear",
            on_click=ResearchState.clear_research,
            variant="outline",
            size="2",
        ),
        spacing="3",
        wrap="wrap",
    )


def ticker_header() -> rx.Component:
    """Ticker information header."""
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.heading(ResearchState.selected_ticker, size="6"),
                rx.cond(
                    ResearchState.current_price,
                    rx.badge(
                        rx.text("$", ResearchState.current_price),
                        color_scheme="green",
                        size="2",
                    ),
                    rx.fragment(),
                ),
                spacing="3",
                align="center",
            ),
            rx.text(
                ResearchState.ticker_info.get("name", ""),
                size="2",
                color_scheme="gray",
            ),
            align="start",
            spacing="1",
        ),
        rx.spacer(),
        rx.vstack(
            rx.text(
                ResearchState.ticker_info.get("sector", ""),
                size="1",
                color_scheme="gray",
            ),
            rx.text(
                ResearchState.ticker_info.get("industry", ""),
                size="1",
                color_scheme="gray",
            ),
            align="end",
            spacing="0",
        ),
        width="100%",
    )


def synthesis_card() -> rx.Component:
    """LLM-generated synthesis card."""
    return rx.cond(
        ResearchState.is_generating_synthesis,
        rx.card(
            rx.hstack(
                rx.spinner(size="2"),
                rx.text("Generating AI analysis...", size="2", color_scheme="gray"),
                spacing="2",
            ),
            width="100%",
        ),
        rx.cond(
            ResearchState.llm_synthesis != "",
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon("sparkles", size=16, color="var(--purple-9)"),
                        rx.heading("AI Analysis", size="4"),
                        rx.spacer(),
                        rx.badge(
                            UserContextState.profile_display_name,
                            variant="soft",
                            color_scheme="purple",
                        ),
                        width="100%",
                        align="center",
                    ),
                    rx.divider(),
                    rx.text(ResearchState.llm_synthesis, size="2", white_space="pre-wrap"),
                    spacing="3",
                    width="100%",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
    )


def overview_tab() -> rx.Component:
    """Overview tab content with quality and analyst cards."""
    return rx.vstack(
        synthesis_card(),
        rx.grid(
            quality_card(),
            analyst_card(),
            columns="2",
            spacing="4",
            width="100%",
        ),
        range_card(),
        spacing="4",
        width="100%",
    )


def charts_tab() -> rx.Component:
    """Charts tab content."""
    return rx.vstack(
        chart_card(),
        spacing="4",
        width="100%",
    )


def news_tab() -> rx.Component:
    """News tab content."""
    return rx.vstack(
        news_card(),
        spacing="4",
        width="100%",
    )


def research_tabs() -> rx.Component:
    """Tabbed research content."""
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Overview", value="overview"),
            rx.tabs.trigger("Charts", value="charts"),
            rx.tabs.trigger("News", value="news"),
        ),
        rx.tabs.content(
            overview_tab(),
            value="overview",
            padding_top="4",
        ),
        rx.tabs.content(
            charts_tab(),
            value="charts",
            padding_top="4",
        ),
        rx.tabs.content(
            news_tab(),
            value="news",
            padding_top="4",
        ),
        value=ResearchState.selected_tab,
        on_change=ResearchState.set_selected_tab,
        width="100%",
    )


def insights_card() -> rx.Component:
    """Profile-specific insights card."""
    return rx.cond(
        ResearchState.profile_insights.length() > 0,
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.icon("lightbulb", size=16, color="var(--amber-9)"),
                    rx.heading("Insights", size="4"),
                    rx.spacer(),
                    rx.badge(
                        UserContextState.profile_display_name,
                        variant="soft",
                        color_scheme="amber",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.divider(),
                rx.foreach(
                    ResearchState.profile_insights,
                    lambda insight: rx.text(insight, size="2"),
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        rx.fragment(),
    )


def research_results() -> rx.Component:
    """Research results display."""
    return rx.cond(
        ResearchState.has_results,
        rx.vstack(
            ticker_header(),
            insights_card(),
            rx.divider(),
            research_tabs(),
            spacing="4",
            width="100%",
        ),
        rx.cond(
            ResearchState.error_message != "",
            rx.callout(
                ResearchState.error_message,
                icon="circle-alert",
                color_scheme="red",
            ),
            rx.center(
                rx.vstack(
                    rx.icon("search", size=48, color="var(--gray-8)"),
                    rx.text("Enter a ticker symbol to begin research", color_scheme="gray"),
                    rx.text(
                        "Try AAPL, NVDA, ORCL, or any stock ticker",
                        size="1",
                        color_scheme="gray",
                    ),
                    spacing="2",
                    align="center",
                ),
                padding="8",
            ),
        ),
    )


def research_content() -> rx.Component:
    """Research page content."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Research", size="6"),
            rx.spacer(),
            rx.badge(
                rx.text("Profile: ", UserContextState.profile_display_name),
                variant="soft",
            ),
            width="100%",
        ),
        research_header(),
        rx.divider(),
        research_results(),
        spacing="4",
        width="100%",
    )


@rx.page(route="/research", title="Research | Phinan Finance Suite", on_load=AppState.set_page("research"))
def research_page() -> rx.Component:
    """Research page."""
    return main_layout(research_content())
