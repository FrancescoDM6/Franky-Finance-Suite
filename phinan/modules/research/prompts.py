"""LLM prompt templates for research module.

These prompts are strategy-aware and provide context-specific
analysis based on the user's trading profile.
"""


STRATEGY_ANALYSIS_PROMPT = """Analyze {ticker} for a {strategy_type} options trader.

Company: {company_name}
Current Price: ${current_price}
Range Position: {range_position} ({range_percent}% of {range_period} range)
Analyst Rating: {analyst_rating}
Target Price: ${target_price}
Quality Assessment: {quality_overall}
Quality Flags: {quality_flags}

Recent News Sentiment: {news_sentiment}

Available Options Chain Data:
{options_context}

IMPORTANT: When recommending specific options trades, use the EXACT expiration dates shown above (e.g., "{expiration_date}"). Do not invent or modify dates.
{portfolio_context}
User Profile:
- Strategy: {profile_description}
- Typical timeframe: {timeframe}
- Default range: {default_range}

Respond in this exact markdown format:

## Executive Summary
[2-3 sentences on overall thesis - is this a buy, hold, or avoid? What's the main story?]

## Bull Case
- [Key bullish factor 1]
- [Key bullish factor 2]

## Bear Case
- [Key bearish factor 1]
- [Key bearish factor 2]

## Actionable Plan
For {strategy_type}'s {timeframe} timeframe:
1. **Primary trade:** [Specific action - be direct about direction and timing]
2. **Alternative:** [Backup approach if primary doesn't work out]
{portfolio_guidance}
Be direct and specific with strikes and timeframes that match the user's style.
"""


BANK_REC_EVAL_PROMPT = """The user received this recommendation from their private bank:

{bank_recommendation}

Based on current research data:
- Ticker: {ticker}
- Current Price: ${current_price}
- Range Position: {range_position}
- Analyst Rating: {analyst_rating}
- Quality Assessment: {quality_overall}
- Recent News Sentiment: {news_sentiment}

User's trading style: {strategy_type}

Evaluate:
1. Does this recommendation align with current fundamentals?
2. Is the timing good (check range position, volatility, recent news)?
3. What might the bank not be telling them?
4. Does this fit the user's {strategy_type} approach?

Be direct about whether this looks like a good idea or not.
"""


THEME_RESEARCH_PROMPT = """User wants to explore investment theme: {theme}

Tax considerations: {tax_notes}
Risk tolerance: {risk_tolerance}
Margin rate for dividend arbitrage: {margin_rate}%

Find opportunities that:
- Meet quality standards (profitable, reasonable debt, industry leaders)
- Have dividend yield > {margin_rate}% for margin strategy (if applicable)
- Match {strategy_type} timeframe ({timeframe})

Consider:
- Current market conditions for this theme
- Specific tickers that fit the criteria
- Entry timing based on range positions

Present top 3 candidates with specific reasoning for each.
"""


def build_analysis_prompt(
    ticker: str,
    ticker_info: dict,
    price_range: dict,
    analyst_data: dict,
    quality_check: dict,
    news_sentiment: str,
    profile_name: str,
    profile_description: str,
    timeframe: str,
    default_range: str,
    portfolio_position: dict = None,
    options_summary: str = "",
    options_expiration: str = "",
) -> str:
    """Build the strategy analysis prompt with all data filled in.
    
    Args:
        portfolio_position: Optional dict with keys: quantity, cost_basis, current_price, gain_loss_percent
    """
    # Build portfolio context if user owns this stock
    portfolio_context = ""
    portfolio_guidance = ""
    if portfolio_position:
        qty = portfolio_position.get("quantity", 0)
        cost = portfolio_position.get("cost_basis", 0)
        pl_pct = portfolio_position.get("gain_loss_percent", 0)
        portfolio_context = f"""
User's Position:
- Holds {qty:,.2f} shares at ${cost:,.2f} cost basis
- Current P/L: {pl_pct:+.1f}%
"""
        if pl_pct > 50:
            portfolio_guidance = "\nNote: User has significant gains. Consider mentioning profit-taking or protective strategies."
        elif pl_pct < -20:
            portfolio_guidance = "\nNote: User is underwater on this position. Consider mentioning recovery strategies or tax-loss harvesting."
        else:
            portfolio_guidance = "\nNote: Factor in the user's existing position when suggesting trades."
    
    return STRATEGY_ANALYSIS_PROMPT.format(
        ticker=ticker,
        strategy_type=profile_name,
        company_name=ticker_info.get("name") or "Unknown",
        current_price=f"{ticker_info.get('current_price') or 0:.2f}",
        range_position=_get_range_position_label(price_range.get("percent_of_range") or 0.5),
        range_percent=int((price_range.get("percent_of_range") or 0.5) * 100),
        range_period=price_range.get("period") or "3mo",
        analyst_rating=analyst_data.get("rating") or "N/A",
        target_price=f"{analyst_data.get('target_price') or 0:.2f}",
        quality_overall=quality_check.get("overall") or "N/A",
        quality_flags=", ".join(quality_check.get("flags") or []),
        news_sentiment=news_sentiment or "No sentiment data",
        portfolio_context=portfolio_context,
        profile_description=profile_description,
        timeframe=timeframe,
        default_range=default_range,
        portfolio_guidance=portfolio_guidance,
        options_context=options_summary or "No options data available.",
        expiration_date=options_expiration or "the date shown",
    )


def build_bank_rec_prompt(
    bank_recommendation: str,
    ticker: str,
    ticker_info: dict,
    price_range: dict,
    analyst_data: dict,
    quality_check: dict,
    news_sentiment: str,
    strategy_type: str,
) -> str:
    """Build the bank recommendation evaluation prompt."""
    return BANK_REC_EVAL_PROMPT.format(
        bank_recommendation=bank_recommendation,
        ticker=ticker,
        current_price=ticker_info.get("current_price") or 0,
        range_position=_get_range_position_label(price_range.get("percent_of_range") or 0.5),
        analyst_rating=analyst_data.get("rating") or "N/A",
        quality_overall=quality_check.get("overall") or "N/A",
        news_sentiment=news_sentiment,
        strategy_type=strategy_type,
    )


def build_theme_prompt(
    theme: str,
    tax_notes: str,
    risk_tolerance: str,
    margin_rate: float,
    strategy_type: str,
    timeframe: str,
) -> str:
    """Build the theme research prompt."""
    return THEME_RESEARCH_PROMPT.format(
        theme=theme,
        tax_notes=tax_notes or "No specific tax considerations provided",
        risk_tolerance=risk_tolerance,
        margin_rate=margin_rate,
        strategy_type=strategy_type,
        timeframe=timeframe,
    )


def _get_range_position_label(percent: float) -> str:
    """Convert range percentage to descriptive label."""
    if percent > 0.8:
        return "Near range high"
    elif percent < 0.2:
        return "Near range low"
    else:
        return "Mid-range"
