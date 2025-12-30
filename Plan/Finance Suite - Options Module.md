---
aliases:
  - options research
  - options tracker
  - weekly options
status: Planned
ai_summary: "Options research and tracking module for Finance Suite. Supports weekly options plays with screening, risk/reward analysis, trade logging, and performance tracking. Designed to compete with dad/uncle's returns and surface patterns in what's working."
priority: Medium
start_date:
end_date:
progress: 0
energy: Medium
domain:
  - Web
  - AI
  - Finance
stage: Planning
iec_score: 7
iec_impact: 8
iec_ease: 6
iec_confidence: 7
blocked: true
blocker: "Build research module first - options module depends on company research data"
files:
links:
integration_notes: "Lives in modules/options/. Depends on research module for underlying analysis. Uses shared market_data service for options chains. DuckDB for trade logging and performance tracking."
integration_status: Planned
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Reflex
  - Python
  - yfinance
  - DuckDB
  - Plotly
categories:
  - "[[Projects]]"
  - "[[Finance]]"
tags:
  - project
  - finance
  - options
  - python
  - trading
DateCreated: Saturday, December 28th 2024
DateLastModified: Saturday, December 28th 2024
---

## Overview

Options research and tracking module focused on weekly plays. The goal: compete with (and hopefully beat) dad/uncle's options returns, or at least demonstrate a more systematic approach.

**Why this matters:**
- Weekly options = weekly data points (fast validation)
- Visible competition gets family attention (vs. asking permission)
- Paper trading works fine for comparison - percentages matter, not absolute dollars
- Surfaces patterns in what's working over time

## Features

### MVP (v0.1)
- [ ] Options chain viewer (from yfinance)
- [ ] Basic payoff diagram for single-leg strategies
- [ ] Trade logging (manual entry)
- [ ] Simple P&L tracking

### v0.2
- [ ] Multi-leg strategy builder (spreads, condors, etc.)
- [ ] Greeks display (delta, gamma, theta, vega)
- [ ] Break-even and probability of profit calculations
- [ ] Historical trade analysis ("your winners vs. losers patterns")

### v0.3
- [ ] Screener/scanner (unusual volume, IV rank, etc.)
- [ ] Alerts for watched setups
- [ ] LLM analysis of trade history ("you tend to lose on X type of plays")
- [ ] Integration with research module ("research this underlying")

### v0.4
- [ ] Paper trading simulation mode
- [ ] Side-by-side comparison with dad/uncle's logged trades
- [ ] Weekly performance reports

## Core Components

### 1. Options Chain Viewer
Pull options data from yfinance:
```python
ticker = yf.Ticker("AAPL")
expirations = ticker.options  # Available dates
chain = ticker.option_chain("2024-01-19")  # Specific date
calls = chain.calls
puts = chain.puts
```

Display:
- Strike prices
- Bid/ask spread
- Volume and open interest
- Implied volatility
- Greeks (if available, may need to calculate)

### 2. Payoff Diagram Generator
For any strategy, show:
- Profit/loss at various underlying prices at expiration
- Break-even point(s)
- Max profit / max loss
- Current underlying price marker

Strategies to support:
- Long call / Long put
- Covered call
- Cash-secured put
- Vertical spreads (bull call, bear put, etc.)
- Iron condor
- Straddle / strangle

### 3. Trade Logger
Schema:
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    underlying TEXT NOT NULL,
    strategy TEXT NOT NULL,  -- 'long_call', 'covered_call', etc.
    entry_date DATE NOT NULL,
    exit_date DATE,
    expiration DATE NOT NULL,
    strike REAL NOT NULL,
    contracts INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    status TEXT DEFAULT 'open',  -- 'open', 'closed', 'expired'
    result REAL,  -- P&L when closed
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Performance Dashboard
Metrics:
- Win rate (% of trades profitable)
- Average win vs. average loss
- Expectancy (avg win * win rate - avg loss * loss rate)
- Total P&L
- P&L by strategy type
- P&L by underlying
- Time-based analysis (best/worst days, holding periods)

### 5. Screener (later)
Scan for:
- Unusual options volume (vs. average)
- High IV rank (options are "expensive")
- Low IV rank (options are "cheap")
- Earnings plays (upcoming announcements)
- Specific strategy setups (e.g., good risk/reward covered calls)

Data challenge: yfinance is limited. May need Polygon or similar for better screening data.

## LLM Use Cases

### Trade Review
```
Analyze this trade:

{trade_details}

Outcome: {result}

What went right or wrong? What could have been done differently? Be specific and constructive.
```

### Pattern Analysis
```
Here are my last 50 options trades:

{trade_history}

Identify patterns:
1. What types of trades am I winning/losing most?
2. Are there underlying-specific patterns?
3. Are there timing patterns (day of week, days to expiration)?
4. What's one actionable change I should consider?
```

### Strategy Suggestion
```
Given this underlying analysis:

{research_summary}

And current options chain:

{chain_summary}

Suggest 2-3 options strategies that fit a {risk_tolerance} risk tolerance and {timeframe} timeframe. Explain the thesis for each.
```

## UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Options Research                                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Ticker: AAPL ▼]  [Expiration: Jan 19 ▼]  [Refresh]   │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ CALLS                    │ PUTS                     ││
│  │ Strike  Bid   Ask   IV   │ Strike  Bid   Ask   IV   ││
│  │ 180    6.20  6.35  28%  │ 180    1.15  1.25  29%  ││
│  │ 185    3.40  3.55  27%  │ 185    2.85  2.95  28%  ││
│  │ 190    1.45  1.55  26%  │ 190    5.60  5.75  27%  ││
│  │ [Select for analysis]    │ [Select for analysis]    ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Strategy Builder                                    ││
│  │ [Long Call ▼]  Strike: [185]  Contracts: [1]       ││
│  │                                                     ││
│  │ Entry cost: $355        Max profit: Unlimited       ││
│  │ Break-even: $188.55     Max loss: $355             ││
│  │ PoP: ~42%                                          ││
│  │                                                     ││
│  │ [Payoff diagram here]                              ││
│  │                                                     ││
│  │ [Log This Trade]                                   ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Trade Log & Performance                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Open Trades]  [Closed Trades]  [Performance]         │
│                                                         │
│  Win Rate: 58%    Avg Win: $245    Avg Loss: $180      │
│  Expectancy: $67/trade    Total P&L: +$1,340           │
│                                                         │
│  Recent Trades:                                         │
│  │ AAPL 185C │ +$120 │ Closed Jan 15 │ [Details]      │
│  │ MSFT 375P │ -$85  │ Expired       │ [Details]      │
│  │ NVDA 480C │ Open  │ Exp Jan 26    │ [Details]      │
│                                                         │
│  [Export]  [Analyze with AI]                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
modules/options/
├── __init__.py
├── page.py           # Main page (may split into subpages)
├── state.py          # OptionsState
├── components.py     # Chain viewer, payoff chart, trade cards
├── strategies.py     # Payoff calculations, greeks
├── screener.py       # Scanning logic (later)
├── logger.py         # Trade CRUD operations
└── prompts.py        # LLM prompt templates
```

## Dependencies

- **Research module**: Link to underlying analysis
- **market_data service**: Options chain data
- **db service**: Trade persistence
- **llm service**: Trade analysis

## Current Action Items

- [ ] Wait for research module MVP
- [ ] Design trade logging schema
- [ ] Implement basic options chain viewer
- [ ] Build payoff diagram component
- [ ] Create trade entry form

## Validation Plan

**Phase 1: Logging only**
- Log dad/uncle's trades (if they share)
- Log my own paper trades
- Build baseline data

**Phase 2: Analysis**
- Run pattern analysis on accumulated trades
- Identify what's working, what's not
- Adjust approach based on data

**Phase 3: Competition**
- Actively use tool to make picks
- Compare weekly performance
- Rub it in their faces when winning 😈

## Related

- [[Finance Suite]] (parent)
- [[Finance Suite - Research Module]] (provides underlying analysis)
- [[Finance Suite - Portfolio Module]] (rolls up options P&L)

---
Created: 2024-12-28
