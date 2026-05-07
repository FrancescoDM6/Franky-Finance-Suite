"""Research page - Company research for options trading."""

import reflex as rx

from ...components.layout import main_layout
from ...state.user_context import UserContextState
from .state import ResearchState
from .components import quality_card, analyst_card, range_card, news_card, chart_card, options_card, volatility_card
from ..portfolio.state import PortfolioState


def research_header() -> rx.Component:
    """Research page header with input and controls."""
    return rx.hstack(
        rx.vstack(
            rx.input(
                placeholder="Enter ticker (e.g., AAPL)",
                value=ResearchState.ticker_input,
                on_change=ResearchState.set_ticker_input,
                on_key_down=ResearchState.handle_search_key,
                size="2",
                width=rx.breakpoints({"0px": "100%", "640px": "200px"}),
                list="tickers",
            ),
            rx.el.datalist(
                rx.foreach(
                    ResearchState.ticker_options,
                    lambda option: rx.el.option(value=option),
                ),
                id="tickers",
            ),
            width=rx.breakpoints({"0px": "100%", "640px": "auto"}),
        ),
        rx.button(
            rx.icon("search", size=16),
            "Research",
            on_click=ResearchState.research_ticker,
            loading=ResearchState.is_loading,
            color_scheme="blue",
            size="2",
            class_name="shark-hover",
        ),
        rx.button(
            "Clear",
            on_click=ResearchState.clear_research,
            variant="outline",
            size="2",
            class_name="shark-hover",
        ),
        spacing="3",
        wrap="wrap",
        width="100%",
    )


def ticker_header() -> rx.Component:
    """Ticker information header."""
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.heading(ResearchState.selected_ticker, size="6"),
                rx.cond(
                    ResearchState.current_price,
                    rx.text(
                        "$", ResearchState.current_price,
                        size="5",
                        weight="bold",
                        color="var(--green-11)",
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
        rx.hstack(
            rx.button(
                rx.icon("star", size=16),
                "Watch",
                on_click=ResearchState.add_to_watchlist,
                variant="soft",
                color_scheme="amber",
                size="2",
            ),
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
            spacing="3",
            align="center",
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
                    rx.markdown(
                        ResearchState.safe_llm_synthesis,
                        component_map={
                            "h1": lambda text: rx.heading(text, size="3", margin_top="0.05em", margin_bottom="0.05em"),
                            "h2": lambda text: rx.heading(text, size="2", margin_top="0.05em", margin_bottom="0.05em"),
                            "h3": lambda text: rx.heading(text, size="2", weight="bold", margin_top="0.05em", margin_bottom="0.05em"),
                            "p": lambda text: rx.text(text, size="1", margin_bottom="0.05em"),
                            "li": lambda text: rx.text(text, size="1", display="list-item", margin_left="1em"),
                        },
                    ),
                    spacing="1",
                    width="100%",
                ),
                width="100%",
            ),
            # Show placeholder if generation failed but we have results
            rx.cond(
                ResearchState.has_results,
                rx.card(
                    rx.vstack(
                         rx.hstack(
                            rx.icon("sparkles", size=16, color="var(--gray-9)"),
                            rx.heading("AI Analysis", size="4", color_scheme="gray"),
                            rx.spacer(),
                            width="100%",
                            align="center",
                        ),
                         rx.text(
                            rx.cond(
                                ResearchState.synthesis_error != "",
                                ResearchState.synthesis_error,
                                "Analysis unavailable. Click 'Research' to try again.",
                            ),
                            size="2",
                            color_scheme="gray",
                            font_style="italic",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    width="100%",
                    variant="surface",  # lighter look for empty state
                    color_scheme="gray",
                ),
                rx.fragment(),
            ),
        ),
    )


def my_position_card() -> rx.Component:
    """Card showing user's position in this stock (if any)."""
    return rx.cond(
        PortfolioState.position_tickers.contains(ResearchState.selected_ticker),
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.icon("briefcase", size=18, color="var(--accent-9)"),
                    rx.heading("My Position", size="4"),
                    rx.spacer(),
                    rx.badge("Owned", color_scheme="green", variant="soft"),
                    width="100%",
                    align="center",
                ),
                rx.text(
                    "You hold this stock. The AI analysis above factors in your position.",
                    size="2",
                    color_scheme="gray",
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
        ),
        # Not owned - show "Add to Portfolio" option
        rx.cond(
            ResearchState.has_results,
            rx.card(
                rx.hstack(
                    rx.vstack(
                        rx.text("Track this stock?", size="2", weight="medium"),
                        rx.text(
                            "Add to your portfolio to get personalized insights.",
                            size="1",
                            color_scheme="gray",
                        ),
                        align="start",
                        spacing="1",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon("plus", size=14),
                        "Add to Portfolio",
                        variant="soft",
                        size="1",
                        on_click=rx.redirect("/portfolio"),
                    ),
                    width="100%",
                    align="center",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
    )


def overview_tab() -> rx.Component:
    """Overview tab content with quality and analyst cards."""
    return rx.vstack(
        rx.cond(
            ResearchState.llm_synthesis == "",
            insights_card(),
            rx.fragment(),
        ),
        rx.grid(
            quality_card(),
            analyst_card(),
            columns=rx.breakpoints({"0px": "1", "768px": "2"}),
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


def options_tab() -> rx.Component:
    """Options tab content."""
    return rx.flex(
        options_card(),
        volatility_card(),
        direction=rx.breakpoints({"0px": "column", "768px": "row"}),
        spacing="4",
        width="100%",
    )


def research_tabs() -> rx.Component:
    """Tabbed research content."""
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Overview", value="overview"),
            rx.tabs.trigger("Charts", value="charts"),
            rx.tabs.trigger("Options", value="options"),
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
            options_tab(),
            value="options",
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
        ResearchState.is_loading,
        # Loading state - show spinner with stage text
        rx.center(
            rx.vstack(
                rx.spinner(size="3"),
                rx.text(ResearchState.loading_stage, size="3", weight="bold", color_scheme="blue"),
                rx.text("Please wait while we gather data...", size="2", color_scheme="gray"),
                spacing="4",
                align="center",
            ),
            padding="40px",
            width="100%",
        ),
        # Not loading - check for results or error
        rx.cond(
            ResearchState.has_results,
            # Has results - show research data
            rx.vstack(
                ticker_header(),
                synthesis_card(),
                my_position_card(),
                rx.divider(),
                research_tabs(),
                spacing="4",
                width="100%",
            ),
            # No results - check for error or empty state
            rx.cond(
                ResearchState.error_message != "",
                # Error state
                rx.callout(
                    ResearchState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                ),
                # Empty state - prompt to search
                rx.center(
                    rx.vstack(
                        # Custom Shark Fin Icon (Large Empty State)
                        rx.html(
                            """
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--gray-8)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                                <!-- Fin Body -->
                                <path d="M 4 20 C 10 18 16 11 19 6 Q 23 13 20 20" />
                                <!-- Detached Chevron -->
                                <polyline points="16 3 22 3 23 8" />
                            </svg>
                            """
                        ),
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



@rx.page(
    route="/research",
    title="Research | Phinan Finance Suite",
    on_load=[UserContextState.load_context, PortfolioState.load_positions, ResearchState.check_pending_search],
)
def research_page() -> rx.Component:
    """Research page."""
    return main_layout(research_content())

