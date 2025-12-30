---
aliases:
  - finance assistant
  - ai assistant
  - finance agent
status: In progress
ai_summary: "Persistent AI assistant serving as the primary interface for the Finance Suite. Maintains user context (watchlist, preferences, trade history), routes requests to modules, synthesizes information across tools, and enables natural conversation about financial decisions. Built on Ollama with tool-calling capabilities."
priority: High
start_date: 2024-12-28
end_date:
progress: 0
energy: High
domain:
  - AI
  - Agents
  - Finance
stage: Design
iec_score: 9
iec_impact: 10
iec_ease: 6
iec_confidence: 8
blocked: false
blocker:
files:
links:
integration_notes: "Core interface layer. Has tools that map to all modules. Maintains persistent user context in DuckDB. Chat UI embedded in main app shell, accessible from any page."
integration_status: Planned
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Python
  - Ollama
  - DuckDB
  - Reflex
categories:
  - "[[Projects]]"
  - "[[AI]]"
  - "[[Finance]]"
tags:
  - project
  - ai
  - agents
  - llm
  - finance
DateCreated: Monday, December 30th 2024
DateLastModified: Monday, December 30th 2024
---

## Overview

The Finance Assistant is the primary way users interact with the suite. Instead of navigating to different pages and filling out forms, you talk to it.

**Why an assistant (not just modules):**
- Modules are powerful but siloed. Research doesn't know about your trades. Options doesn't know what notes you're considering.
- The assistant has **persistent context** - it knows your watchlist, your preferences, your history.
- Natural language is faster for exploration: "What do you think about NVDA?" vs. navigating to research, typing ticker, reading output.
- Multi-turn conversations let you drill down: "What about the puts specifically?" → "Compare to AAPL puts" → "Log that trade idea"

**What makes this different from ChatGPT:**
- Grounded in real, current data (via tools that hit live APIs)
- Access to your personal data (trade history, watchlist, preferences)
- Runs locally (Ollama) - private, no API costs
- Domain-specific tools designed for this workflow

## User Context

The assistant maintains persistent knowledge about the user:

```python
@dataclass
class UserContext:
    user_id: str
    risk_tolerance: str  # "conservative" or "aggressive"
    typical_strategy: str  # "entry_exit" or "directional"
    typical_timeframe: str  # "2_weeks" or "1_2_months"
    preferences: list[str]
    avoid_list: list[str]
    watchlist: list[str]
    open_positions: list[Position]
    notes_under_review: list[StructuredNote]
    trade_history: list[Trade]
```

This context is loaded at conversation start, updated as user takes actions, persisted to DuckDB, and injected into system prompt.

## Available Tools

### Research Tools
| Tool | Purpose |
|------|---------|
| `lookup_ticker(symbol, range_period)` | Full research: quality, range, IV, thesis |
| `compare_tickers(symbols)` | Side-by-side comparison |
| `get_news(symbol, days)` | Recent news with sentiment |
| `find_similar(symbol)` | Embedding-based similarity search |

### Notes Tools
| Tool | Purpose |
|------|---------|
| `analyze_note(terms)` | Full analysis: fees, risks, simulations |
| `parse_note_pdf(file)` | OCR extraction of terms |
| `simulate_scenarios(note, scenarios)` | What-if modeling |
| `compare_to_alternatives(note, capital)` | vs. covered calls, bonds, options |

### Options Tools
| Tool | Purpose |
|------|---------|
| `get_options_chain(symbol, exp)` | Chain with IV, greeks, anomalies |
| `calculate_strategy(legs)` | Payoff, break-evens, PoP |
| `log_trade(trade)` | Save to history |
| `get_trade_history(filters)` | Query past trades |
| `analyze_trade_patterns()` | Find patterns in your history |

### Portfolio & Utility Tools
| Tool | Purpose |
|------|---------|
| `get_positions()` | Current open positions |
| `get_performance(period)` | P&L, win rate, attribution |
| `add_to_watchlist(symbol)` | Track a ticker |
| `set_preference(key, value)` | Update user prefs |

## Example Conversations

### Research Flow
```
User: What do you think about NVDA this week?
Assistant: [calls lookup_ticker("NVDA", range_period="3mo")]

NVDA is at $495, sitting at 72% of its 3-month range ($420-$505). Quality looks 
strong - profitable, reasonable debt, dominant market position.

For weekly options:
- Weekly ATR is ~$18 (3.6%), expected range roughly $477-$513
- IV rank at 45% - premiums moderate
- No earnings until Feb 21

You traded NVDA twice last month - won both with weekly puts. No current position.

Near top of range - if playing "stay in range", the $505-510 calls could work 
for premium selling. Want me to pull up the chain?

User: Show me the 6-month range instead
Assistant: [calls lookup_ticker("NVDA", range_period="6mo")]

Over 6 months, NVDA has ranged $390-$505. Currently at 78% of that range.
The wider view shows more room to run - $505 was resistance back in August too.

User: Yeah show me the weeklies