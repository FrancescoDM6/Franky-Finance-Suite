---
aliases:
  - research dashboard
  - company research
  - ticker research
status: In progress
ai_summary: "Company research dashboard supporting two distinct options strategies: (1) Papi's conservative approach using options as entry/exit mechanism on quality stocks, (2) Tio's aggressive traditional options plays with deeper research. Surfaces analyst ratings, recent news momentum, dividend yields for margin strategy, and configurable range analysis."
priority: High
start_date: 2024-12-28
end_date:
progress: 0
energy: High
domain:
  - Web
  - AI
  - Finance
stage: Design
iec_score: 8.5
iec_impact: 9
iec_ease: 7
iec_confidence: 9
blocked: false
blocker:
files:
links:
integration_notes: "Lives in modules/research/. Uses shared services (market_data, llm, news, sentiment). Supports two user profiles with different data emphasis. Assistant can invoke via lookup_ticker, compare_tickers, get_news tools."
integration_status: Planned
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Reflex
  - Python
  - Ollama
  - yfinance
categories:
  - "[[Projects]]"
  - "[[Finance]]"
tags:
  - project
  - finance
  - ai
  - python
  - research
  - options
DateCreated: Saturday, December 28th 2024
DateLastModified: Monday, December 30th 2024
---

## Overview

Company research dashboard supporting two distinct options trading strategies used by the family.

## The Two Strategies

### Papi's Strategy (Conservative)
**Core Philosophy:** Options as entry/exit mechanism, not speculation. Only trades stocks he owns or would want to own.

| Action | When | Example |
|--------|------|---------|
| Sell calls | Owns stock, doesn't expect big upside | Own ORCL, sell calls because not expecting large move up |
| Buy puts | Wants to own stock, wants cheaper entry | Buy NBIS puts because wants to own it at lower price |

**Characteristics:**
- Short timeframes (~2 weeks)
- Uses recent highs as reference for call strikes (3-month, 6-month, configurable)
- Takes cost basis into account (recoup cost of buying stock)
- Research: industry leaders, analysts, recent news

### Tio's Strategy (Aggressive)
**Core Philosophy:** Traditional risk-taking with options for leverage.

| Action | When |
|--------|------|
| Buy calls | Bullish on stock |
| Sell puts | Wants premium, willing to own at strike |

**Characteristics:**
- Larger contracts
- Longer timeframes (1-2 months)
- Much deeper research (higher risk demands it)
- Uses structured notes for truly long-term plays
- More exposed to momentum and news catalysts

### Shared Infrastructure
Both use private banking margin with a dividend arbitrage strategy:
- Bank charges ~3% on margin
- Target stocks paying 5%+ dividends
- Net result: keep 2% spread while having exposure

Bank also sends:
1. **Portfolio-based recommendations** - based on current holdings
2. **Analysis-based recommendations** - stocks to look at, specific trade ideas
3. **Theme reports** on request (e.g., "emerging markets")

## What the Tool Needs to Surface

### For Both Strategies

| Data Point | Why It Matters |
|------------|----------------|
| "Would I own this?" quality check | Core filter for Papi, risk assessment for Tio |
| Configurable price range (3mo, 6mo, custom) | Strike price selection, range-bound thesis |
| Analyst ratings & predictions | Both rely on this for direction |
| Recent news (today/yesterday) | Momentum factor, both check this |
| Dividend yield | Margin arbitrage strategy |
| Industry position | Looking for leaders |

### Papi-Specific
| Data Point | Why It Matters |
|------------|----------------|
| Cost basis tracking | Needs to recoup stock purchase cost |
| 2-week expected range | Short timeframe strike selection |
| Call premium at range high | Natural strike for covered calls |
| Put premium at target entry | Planning put purchases |

### Tio-Specific
| Data Point | Why It Matters |
|------------|----------------|
| 1-2 month expected range | Longer timeframe |
| Deeper fundamental analysis | Higher risk = more diligence |
| Momentum indicators | More exposed to momentum plays |
| IV rank/percentile | Premium selling timing |
| Comparison to structured notes | "Is this better than a note?" |

## Data Requirements

### Quality Check (Would I Own This?)

| Metric | Source | Purpose |
|--------|--------|---------|
| Market Cap | yfinance | Size/stability |
| Industry Position | Manual/LLM | Is it a leader? |
| P/E Ratio | yfinance | Valuation |
| Profit Margin | yfinance | Actually making money? |
| Debt/Equity | yfinance | Leverage risk |
| **Dividend Yield** | yfinance | **Critical for margin strategy** |
| Dividend Safety | Payout ratio | Can they maintain it? |

### Analyst Data (Both Rely On This)

| Metric | Source | Purpose |
|--------|--------|---------|
| Analyst Rating | yfinance `recommendationKey` | Buy/hold/sell consensus |
| Target Price | yfinance `targetMeanPrice` | Upside/downside |
| # of Analysts | yfinance | Confidence in consensus |
| Recent Revisions | Needs API | Direction of sentiment |
| Earnings Estimates | yfinance | Beat/miss expectations |

### News & Momentum

| Metric | Source | Purpose |
|--------|--------|---------|
| Headlines (24-48hr) | News API | "Way the company is going" |
| Sentiment Score | FinBERT | Quick read on news tone |
| Price Momentum | Calculated | Recent direction |
| Volume vs Average | yfinance | Unusual activity |

### Range Analysis (Configurable)

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| Range High | `history['High'].rolling(period).max()` | Call strike reference |
| Range Low | `history['Low'].rolling(period).min()` | Support level |
| Current vs Range | Percentage | Where are we now? |
| 2-Week Expected Move | ATR-based | Papi's timeframe |
| 1-2 Month Expected Move | GARCH forecast | Tio's timeframe |

**Configurable periods:** 1 month, 3 months, 6 months, 1 year, custom

### Options-Specific

| Metric | Source | Purpose |
|--------|--------|---------|
| ATM IV | Options chain | Current premium level |
| IV Rank | Calculated | Is IV high or low historically? |
| Put Premium @ Target | Options chain | Cost of entry strategy |
| Call Premium @ Range High | Options chain | Covered call income |

## User Profiles

The tool should support switching between profiles that emphasize different data:

```python
@dataclass
class UserProfile:
    name: str
    strategy_type: str  # "conservative" or "aggressive"
    typical_timeframe: str  # "2_weeks" or "1_2_months"
    default_range_period: str  # "3mo", "6mo", etc.
    emphasis: list[str]  # Which sections to highlight
    
PROFILES = {
    "papi": UserProfile(
        name="Papi",
        strategy_type="conservative",
        typical_timeframe="2_weeks",
        default_range_period="3mo",
        emphasis=["dividend_yield", "cost_basis", "range_high_calls", "quality_check"]
    ),
    "tio": UserProfile(
        name="Tio", 
        strategy_type="aggressive",
        typical_timeframe="1_2_months",
        default_range_period="6mo",
        emphasis=["momentum", "analyst_deep_dive", "iv_analysis", "news_sentiment"]
    ),
    "franky": UserProfile(
        name="Franky",
        strategy_type="learning",
        typical_timeframe="varies",
        default_range_period="6mo",
        emphasis=["all"]  # Show everything while learning
    )
}
```

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [Ticker: ______]  [Profile: Papi ▼]  [Range: 3mo ▼] [Research]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ORCL - Oracle Corp                              $124.56 (+1.2%)│
│  Technology | Industry Leader                                   │
│                                                                 │
├─────────────────────┬───────────────────────────────────────────┤
│                     │                                           │
│  QUALITY CHECK ✓    │  ANALYST CONSENSUS                        │
│  ═══════════════    │  ═══════════════                          │
│                     │                                           │
│  Industry: Leader   │  Rating: BUY (14 analysts)               │
│  P/E: 22.4     ✓    │  Target: $142 (+14% upside)              │
│  Profit Mgn: 28% ✓  │  Recent: 3 upgrades, 1 downgrade         │
│  Debt/Eq: 1.2   ✓   │                                           │
│  Div Yield: 1.4% ⚠️ │  Earnings: Jan 15 (12 days)              │
│  Payout: 35%    ✓   │  Est: $1.42 EPS (+8% YoY)                │
│                     │                                           │
│  "Solid quality,    │                                           │
│   div below 3%      │                                           │
│   margin target"    │                                           │
│                     │                                           │
├─────────────────────┴───────────────────────────────────────────┤
│                                                                 │
│  PRICE RANGE (3 Month)                        [1mo|3mo|6mo|1y] │
│  ══════════════════                                             │
│                                                                 │
│  High: $128.50  ←── Potential call strike                      │
│  Low:  $112.30                                                  │
│  Now:  $124.56  [═══════════════════▓░░░] 76% of range         │
│                                                                 │
│  Near range high. Papi thesis: "Not expecting large upside"    │
│  → Good candidate for selling calls                             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  RECENT NEWS (24hr)                              Sentiment: 🟢  │
│  ═════════════════                                              │
│                                                                 │
│  • "Oracle cloud revenue beats estimates" (Reuters, 2hr ago)   │
│  • "ORCL announces expanded AI partnership" (CNBC, 8hr ago)    │
│  • "Database market share grows in Q4" (TechCrunch, 18hr ago)  │
│                                                                 │
│  Momentum: Positive news flow, stock near highs                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OPTIONS SNAPSHOT (Papi's Timeframe: 2 weeks)                  │
│  ═══════════════════════════════════════════                    │
│                                                                 │
│  Call @ $128 (near range high): $1.85 premium  (1.5% in 2wks) │
│  Call @ $130:                   $0.95 premium  (0.8% in 2wks) │
│                                                                 │
│  If own 100 shares @ $110 cost basis:                          │
│  Selling $128 calls = $185 income, called away @ $128 = +$1985 │
│                                                                 │
│  IV Rank: 32% (moderate, not expensive)                        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SUGGESTED ACTIONS                                              │
│  ═════════════════                                              │
│                                                                 │
│  Given: Quality stock, near range high, not expecting upside   │
│                                                                 │
│  → Sell Jan 10 $128 calls @ $1.85                              │
│    Max income: $185/contract                                    │
│    Break-even if called: $129.85                                │
│    Risk: Stock rockets past $128                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## LLM Prompts

### Strategy-Aware Research Prompt
```
Analyze {ticker} for a {strategy_type} options trader.

Company Data:
{company_data}

Analyst Data:
{analyst_data}

Recent News:
{news_summary}

Price Range ({range_period}):
{range_data}

User Context:
- Strategy: {strategy_description}
- Typical timeframe: {timeframe}
- Current holdings: {holdings if relevant}

Provide:
1. Quality assessment (would you own this stock?)
2. Current positioning (where in range, momentum direction)
3. Relevant news takeaway (one sentence)
4. Strategy-specific suggestion:
   - For conservative: entry/exit mechanism opportunities
   - For aggressive: directional play assessment

Be specific with strikes and timeframes that match the user's style.
```

### Bank Recommendation Evaluation
```
The user received this recommendation from their private bank:

{bank_recommendation}

Based on current data:
{current_research}

Evaluate:
1. Does this align with current fundamentals?
2. Is the timing good (check range position, IV, news)?
3. What's the bank potentially not telling them?
4. Would this fit the user's {strategy_type} approach?

Be direct about whether this looks like a good idea or not.
```

### Emerging Markets / Theme Research
```
User wants to explore: {theme}

Tax considerations: {tax_notes}
Risk factors: {risk_factors}

Find opportunities that:
- Meet quality standards
- Have dividend yield > {margin_rate}% (for margin strategy)
- Match {strategy_type} timeframe

Present top 3 candidates with reasoning.
```

## Features by Version

### MVP (v0.1)
- [ ] Single ticker research
- [ ] Quality check metrics
- [ ] Analyst consensus display
- [ ] Configurable range analysis (1mo, 3mo, 6mo, 1y)
- [ ] Basic news feed (no sentiment yet)
- [ ] Single profile (show all data)

### v0.2
- [ ] User profiles (Papi/Tio/Custom)
- [ ] News sentiment scoring (FinBERT)
- [ ] Options snapshot (premiums at key strikes)
- [ ] Strategy-specific suggestions
- [ ] Dividend yield emphasis for margin strategy

### v0.3
- [ ] Multi-ticker comparison
- [ ] Bank recommendation evaluator
- [ ] Theme/sector research mode
- [ ] Cost basis tracking integration
- [ ] Alert system ("ORCL near 3mo high")

### v0.4
- [ ] Deeper analyst data (revision history)
- [ ] Earnings calendar integration
- [ ] Momentum indicators
- [ ] IV historical comparison
- [ ] Export research to PDF

## File Structure

```
modules/research/
├── __init__.py
├── page.py           # Main page component
├── state.py          # ResearchState
├── profiles.py       # User profile definitions
├── components/
│   ├── __init__.py
│   ├── quality_card.py
│   ├── analyst_card.py
│   ├── range_card.py
│   ├── news_card.py
│   ├── options_snapshot.py
│   └── suggestion_card.py
└── prompts.py
```

## Current Action Items

- [x] Document both family strategies in detail
- [x] Make range analysis configurable (not hardcoded to 6mo)
- [ ] Implement basic ResearchState
- [ ] Build quality_card with dividend emphasis
- [ ] Add analyst data fetching
- [ ] Create range visualization with period selector
- [ ] Wire up news feed
- [ ] Test with stocks they've actually traded (ORCL, NBIS)

## Validation Plan

**Phase 1: Data Accuracy**
- Run tool on stocks they've recently traded
- Verify analyst data matches what they see from bank
- Check that news feed catches what they're reading

**Phase 2: Strategy Fit**
- Show Papi a research output, ask "does this help?"
- Show Tio a research output, ask "what's missing?"
- Iterate based on feedback

**Phase 3: Competition**
- Use tool to generate own trade ideas
- Track results vs. their picks
- Demonstrate value with actual returns

## Related

- [[Finance Suite]] (parent)
- [[Finance Suite - Assistant]] (can invoke research tools)
- [[Finance Suite - Options Module]] (uses research for trade decisions)
- [[Finance Suite - Notes Module]] (Tio uses notes for long-term, tool should compare)

---
Created: 2024-12-28
Updated: 2024-12-30 - Added detailed family strategy breakdown, made range analysis configurable
