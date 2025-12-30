---
aliases:
  - structured note analyzer
  - note analyzer
  - structured notes
status: In progress
ai_summary: "Structured note analysis module for Finance Suite. Decomposes opaque bank products to reveal actual fees, risks, and opportunity costs. Features Monte Carlo simulation, fee breakdown, risk scenario modeling, and comparison to simpler alternatives. Has existing prototype code to migrate."
priority: Medium
start_date: 2024-12-28
end_date:
progress: 20
energy: Medium
domain:
  - Web
  - AI
  - Finance
stage: Design
iec_score: 7
iec_impact: 9
iec_ease: 5
iec_confidence: 7
blocked: false
blocker:
files:
links:
integration_notes: "Lives in modules/notes/. Migrating from old Streamlit prototype. Monte Carlo logic is reusable. LLM prompts need adaptation from Gemini to Ollama format."
integration_status: Planned (has prototype)
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Reflex
  - Python
  - Ollama
  - NumPy
  - Plotly
categories:
  - "[[Projects]]"
  - "[[Finance]]"
tags:
  - project
  - finance
  - ai
  - python
  - structured-notes
DateCreated: Saturday, December 28th 2024
DateLastModified: Saturday, December 28th 2024
---

## Overview

Structured notes are intentionally opaque. Banks design them that way to hide fees and make risk/reward comparisons difficult. This module decomposes them into understandable components.

**Family Context:**
- Tio uses structured notes as the long-term equivalent of options plays
- He doesn't use long-term option strikes because notes serve that purpose
- They haven't received many notes lately due to current market conditions
- When market normalizes, notes will flow again from the private bankers
- The tool should help evaluate: "Is this note better than Tio's rolling options alternative?"

**The problem:**
- Dad/uncle receive structured note pitches from private bankers
- Notes promise "consistent income" with "aggressive upside"
- Actual fee structure and risk profile are buried in term sheets
- Hard to compare to simpler alternatives (just buying the underlying, selling covered calls, rolling options, etc.)

**What this module does:**
- Breaks down the actual fee structure
- Models risk scenarios (what causes you to lose money)
- Compares to equivalent simpler strategies
- Runs Monte Carlo simulations on outcomes

**Validation challenge:**
Unlike the research module, you can't validate this weekly. A structured note takes months/years to mature. Focus on *immediately verifiable* outputs:
- Fee calculations can be checked against term sheet
- Risk scenarios can be confirmed logically
- Comparisons are mathematical

## Features

### MVP (v0.1) - Port from prototype
- [ ] Manual input of note terms (underlying, barrier, coupon, maturity)
- [ ] Fee decomposition calculation
- [ ] Risk scenario breakdown
- [ ] Basic Monte Carlo simulation
- [ ] Results display

### v0.2
- [ ] PDF term sheet parsing (LLM-assisted extraction)
- [ ] Comparison to alternatives (covered call, direct equity, bonds)
- [ ] Interactive "what-if" scenario adjustment
- [ ] PDF report export

### v0.3
- [ ] Historical backtest ("how would this note have performed over last 10 years")
- [ ] Multiple underlier support (basket notes)
- [ ] Correlation modeling for baskets
- [ ] Bank recommendation evaluator ("Is this note pitch a good deal?")
- [ ] Compare note to Tio's rolling options alternative

## Note Types to Support

### Autocallable Notes (most common)
- Underlying: Single stock or index
- Barrier: Knock-in level (e.g., 70% of initial)
- Coupon: Periodic payment if conditions met
- Autocall: Early redemption if underlying above threshold
- Maturity: Typically 1-3 years

### Principal Protected Notes
- Guaranteed return of principal
- Participation rate in upside
- Cap on maximum return

### Reverse Convertibles
- High coupon
- Principal at risk if underlying falls below barrier
- Short maturity (typically 3-12 months)

## Core Analysis Components

### 1. Fee Decomposition
```
Inputs: Note terms, current underlying price, risk-free rate, implied volatility

Calculate:
- Theoretical value of embedded option(s)
- Present value of coupon stream
- Difference = bank's embedded fee

Output:
- "This note has ~3.2% embedded fees"
- "Your effective yield after fees is X% vs. advertised Y%"
```

### 2. Risk Scenario Modeling
```
For each risk scenario:
- Probability of occurrence (from Monte Carlo)
- Outcome if it occurs
- Expected loss/gain

Key scenarios:
- Barrier breach (stock drops below knock-in)
- Autocall (early redemption)
- Full term with no breach
- Full term with breach
```

### 3. Monte Carlo Simulation
```python
def simulate_note(underlying, barrier, coupon, maturity, n_sims=10000):
    """
    Simulate underlying price paths using GBM.
    For each path, determine note outcome.
    Return distribution of outcomes.
    """
    # Use historical vol or implied vol
    # Generate price paths
    # Check barrier conditions
    # Calculate payoff for each path
    # Return statistics and distribution
```

### 4. Alternative Comparison
```
Given the same capital and risk tolerance:
- What would a covered call strategy return?
- What would direct equity + stop loss return?
- What would a bond ladder return?
- What would Tio's rolling 1-2 month options plays return?

Present side-by-side with note's expected return.
```

**Note vs. Tio's Options Strategy:**
Since Tio uses structured notes as the long-term equivalent of options, the tool should explicitly compare:
- Note expected return over full term
- Equivalent options strategy return (rolling monthly plays)
- Capital efficiency (notes tie up capital, options use margin)
- Risk profiles (note has defined downside, options can lose 100%)

## LLM Use Cases

### Term Sheet Parsing
```
Extract structured note terms from this document:

{pdf_text}

Return JSON:
{
  "issuer": "...",
  "underlying": "...",
  "initial_level": ...,
  "barrier_level": ...,
  "barrier_type": "...",
  "coupon_rate": ...,
  "coupon_frequency": "...",
  "maturity_date": "...",
  "autocall_levels": [...],
  "autocall_dates": [...]
}
```

### Risk Explanation
```
Explain the following structured note risk scenario in plain language:

{scenario_data}

The audience is an experienced investor who is NOT a derivatives expert. Avoid jargon. Be specific about dollar amounts given a ${investment_amount} investment.
```

### Recommendation
```
Given this structured note analysis:

{analysis_summary}

And these alternative strategies:

{alternatives_comparison}

Provide a balanced assessment. What type of investor/situation would this note make sense for? What would you want to be true about your market outlook to prefer this note over alternatives?

Do not give a buy/don't buy recommendation. Help the investor understand the tradeoffs.
```

## UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Structured Note Analyzer                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Upload PDF] or [Manual Entry]                         │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Note Terms                                          ││
│  │ Underlying: [AAPL    ▼]   Initial: [$185.00]       ││
│  │ Barrier:    [70%      ]   Coupon:  [8.5%   ]       ││
│  │ Maturity:   [18 months]   Autocall:[105%   ]       ││
│  │                                    [Analyze]        ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │ Fee Breakdown        │  │ Risk Scenarios       │    │
│  │                      │  │                      │    │
│  │ Embedded fees: 3.2%  │  │ Barrier breach: 18%  │    │
│  │ Effective yield: 5.1%│  │ Autocall Y1: 42%     │    │
│  │ vs. Advertised: 8.5% │  │ Full term: 31%       │    │
│  │                      │  │ ...                  │    │
│  └──────────────────────┘  └──────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Monte Carlo Results                                 ││
│  │ [Outcome distribution histogram]                    ││
│  │                                                     ││
│  │ Expected return: 4.8%   Median: 5.2%               ││
│  │ 5th percentile: -22%    95th percentile: 8.5%      ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ vs. Alternatives                                    ││
│  │                                                     ││
│  │ Strategy          │ Exp. Return │ Max Loss │ Notes  ││
│  │ This note         │ 4.8%        │ -30%     │        ││
│  │ Covered calls     │ 6.2%        │ -100%    │ More $ ││
│  │ Direct + stop     │ 8.1%        │ -15%     │ Active ││
│  │ Bond ladder       │ 4.5%        │ ~0%      │ Safe   ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  [Generate Report]                                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Migration from Prototype

### What exists (Streamlit version)
- Basic Monte Carlo simulation logic ✓
- Gemini API integration for chat-style analysis
- yfinance price fetching
- PDF generation (reportlab?)
- Floating chat UI (had overlap issues)

### What to migrate
- Monte Carlo core logic → `modules/notes/simulator.py`
- Price fetching → already in shared `services/market_data.py`
- PDF generation → `modules/notes/report.py`

### What to rebuild
- All UI (Streamlit → Reflex)
- LLM integration (Gemini → Ollama)
- State management

### What to drop
- Chat-style interface (moving to structured analysis)
- LangGraph agent orchestration (overengineered, revisit later if needed)

## File Structure

```
modules/notes/
├── __init__.py
├── page.py           # Main page component
├── state.py          # NotesState (terms, results, simulations)
├── components.py     # Input forms, result cards, charts
├── simulator.py      # Monte Carlo engine
├── analyzer.py       # Fee decomposition, risk scenarios
├── comparisons.py    # Alternative strategy calculations
├── parser.py         # PDF term sheet extraction
├── report.py         # PDF report generation
└── prompts.py        # LLM prompt templates
```

## Current Action Items

- [ ] Locate old prototype code in repo
- [ ] Extract Monte Carlo logic, test independently
- [ ] Design NotesState schema
- [ ] Build term input form
- [ ] Wire up simulator
- [ ] Display basic results

## Related

- [[Finance Suite]] (parent)
- [[Finance Suite - Assistant]] (can invoke notes tools)
- [[Finance Suite - AI Services]] (uses PDF extraction, LLM)
- [[Finance Suite - Research Module]] (can research underlying from here)
- [[Finance Suite - Options Module]] (compare notes to rolling options)

---
Created: 2024-12-28
Supersedes: [[Structured Note Simulator App]], [[Agent Finance Orchestration]]
