"""LLM prompt templates for home page features."""


DAILY_BRIEF_PROMPT = """Generate a brief morning summary for {profile_name}.

**Portfolio Status:**
- Total Value: ${total_value:,.2f}
- Total P/L: {total_pl_pct:+.1f}%
- Positions: {position_count}
{position_summary}

**Notable Movers:**
{movers_summary}

**Watchlist Updates:**
{watchlist_summary}

**Recent News for Holdings:**
{news_summary}

Respond in this markdown format:

## Good morning, {profile_name}!

### Portfolio Snapshot
[2-3 sentences on overall portfolio status and any notable positions]

### Today's Watchlist
[1-2 sentences on watchlist movers, if any significant]

### News to Note
[1-2 bullet points on relevant news for holdings]

### {profile_section_title}
[1 actionable insight matching the user's trading style]

Keep the tone conversational but professional. Be concise - this should take 30 seconds to read.
"""


# Profile-specific section titles
PROFILE_SECTIONS = {
    "papi": "Income Opportunities",
    "tio": "Trading Opportunities",
    "franky": "Learning Moment",
}


def build_daily_brief_prompt(
    profile_name: str,
    profile_key: str,
    total_value: float,
    total_pl_pct: float,
    position_count: int,
    position_summary: str,
    movers_summary: str,
    watchlist_summary: str,
    news_summary: str,
) -> str:
    """Build the daily brief prompt with all data filled in."""
    section_title = PROFILE_SECTIONS.get(profile_key.lower(), "Opportunities")

    return DAILY_BRIEF_PROMPT.format(
        profile_name=profile_name,
        total_value=total_value,
        total_pl_pct=total_pl_pct,
        position_count=position_count,
        position_summary=position_summary or "No positions yet.",
        movers_summary=movers_summary or "No significant movers.",
        watchlist_summary=watchlist_summary or "No watchlist items.",
        news_summary=news_summary or "No recent news for holdings.",
        profile_section_title=section_title,
    )
