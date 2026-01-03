# CLAUDE.md

## Before Starting ANY Task

1. ✅ Read `docs/REFLEX_REFERENCE.md` if task involves UI components
2. ✅ Use `view` to check similar existing code
3. ✅ For Reflex syntax questions, search https://reflex.dev/docs/

**Critical Rule**: State variables use `.to(type)`, NEVER `int()`, `str()`, `float()`

## Reflex Framework Knowledge

**IMPORTANT**: Claude's knowledge of Reflex may be outdated or incomplete.

**Before writing ANY Reflex code**, read:
1. `docs/REFLEX_REFERENCE.md` - Curated patterns from official docs
2. Existing components in `phinan/components/` for established patterns
3. When in doubt, use `view` tool to check similar code in the codebase

### Most Common Mistake
Using Python built-ins (`int()`, `str()`, `float()`) instead of `.to()` on State variables.

**Remember**: State variables are `rx.Var` objects that require `.to(type)` for conversion.

## When Reflex Syntax is Unclear

If you encounter a Reflex pattern not covered in `docs/REFLEX_REFERENCE.md`:

1. **Search official docs**: Use web_search for "reflex.dev [specific feature]"
2. **Check existing code**: Use `view` to find similar patterns in the codebase
3. **Ask for clarification**: Tell the user "I'm not certain about this Reflex pattern, let me search the docs"

Example:
```bash
# If unsure about Reflex table syntax
web_search("reflex.dev table component documentation")
```

**Never guess at Reflex syntax** - it's better to search or ask than to use incorrect patterns.

## Project Guidance
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phinan Finance Suite is a personal finance application for investment research, options trading, and portfolio management. The core design: a **persistent AI assistant** is the primary interface, with modules (research, notes, options, portfolio) serving as tools and data layers the assistant can invoke.

## Tech Stack

- **Framework:** Reflex (Python-native, compiles to React)
- **LLM:** Ollama (local, privacy-focused)
- **Database:** DuckDB (embedded, SQL, analytics-optimized)
- **Market Data:** yfinance (free tier, abstracted for future swap to Polygon)
- **Sentiment:** FinBERT (domain-specific, fast)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Volatility:** GARCH via `arch` package
- **Charts:** Plotly

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
reflex run

# Run in production mode
reflex run --env prod

# Run database migrations
python migrations/migration_runner.py

# Deploy to Railway (Production)
# This uses a custom Caddy+Uvicorn setup. Do NOT use `reflex run` in production.
# See README.md for details.
```

## Deployment Architecture (Railway)
- **Frontend**: Served by Caddy (Reverse Proxy + Static Files) at `$PORT`
- **Backend**: Served by Uvicorn at `127.0.0.1:8000` (Direct execution, no Reflex wrapper)
- **State**: Redis (Persistent)
- **Memory**: Optimized by skipping runtime frontend compilation

## Project Structure

```
phinan/
├── __init__.py
├── phinan.py              # Main app entry point
├── config/
│   ├── __init__.py
│   └── settings.py        # Pydantic settings with env vars
├── core/
│   ├── __init__.py
│   └── database.py        # DuckDB manager with thread-safe connections
├── services/
│   ├── __init__.py        # Lazy-loaded service registry
│   ├── llm.py             # Ollama wrapper
│   ├── market_data.py     # yfinance adapter
│   ├── sentiment.py       # FinBERT
│   ├── volatility.py      # GARCH forecasting
│   └── embeddings.py      # sentence-transformers
├── state/
│   ├── __init__.py
│   ├── app.py             # Global app state
│   └── user_context.py    # Persistent user preferences
├── components/
│   ├── __init__.py
│   ├── layout.py          # Main layout with sidebar + assistant
│   ├── navbar.py          # Top navigation
│   ├── sidebar.py         # Navigation sidebar
│   └── assistant/
│       ├── __init__.py
│       ├── state.py       # Assistant chat state
│       └── chat.py        # Chat UI components
├── pages/
│   ├── __init__.py
│   ├── index.py           # Home dashboard
│   └── settings.py        # Settings page
└── modules/
    ├── research/
    │   ├── __init__.py
    │   ├── page.py        # Research page
    │   ├── state.py       # ResearchState
    │   ├── profiles.py    # User profiles (Papi/Tio/Franky)
    │   └── components/    # Quality card, range card, etc.
    ├── notes/             # Structured note analyzer (stub)
    ├── options/           # Options trading (stub)
    └── portfolio/         # Portfolio view (stub)
```

## Key Design Principles

### 1. Use the Right Tool for the Job
- **LLM:** Synthesis, explanation, exploration, multi-turn conversations
- **FinBERT:** Sentiment classification (10-100x faster than LLM, batchable)
- **Python:** All calculations (LLM is bad at math)
- **GARCH:** Volatility forecasting
- **Regex/OCR:** Number extraction from PDFs (LLM hallucinates numbers)

### 2. LLM Extracts, Python Calculates
Never ask the LLM to do math. Have it extract variables, then compute in Python.

### 3. Data Provider Adapter Pattern
yfinance breaks often. Abstract behind an interface for easy swap to Polygon or other providers.

### 4. Service Registry Pattern
```python
from phinan.services import services

# Services lazy-loaded on first access
services.llm.chat(messages=[...])
services.market_data.get_ticker_info("AAPL")
services.db.query("SELECT * FROM portfolio")
```

### 5. Lean State Pattern
Keep Reflex state minimal - store IDs and fetch full objects on demand.
Heavy data (options chains, price history) should come from services/cache.

## Configuration

Settings via environment variables with `PHINAN_` prefix:
```bash
PHINAN_DATABASE_PATH=~/.phinan/phinan.duckdb
PHINAN_OLLAMA_BASE_URL=http://localhost:11434
PHINAN_OLLAMA_MODEL=llama3.2:latest
PHINAN_AI_SERVICES_ENABLE_SENTIMENT=false  # Disable for faster startup
```

See `.env.example` for all options.

## User Profiles

Three trading profiles with different research emphasis:
- **Papi:** Conservative, 2-week options, dividend yield focus
- **Tio:** Aggressive, 1-2 month plays, momentum focus
- **Franky:** Learning mode, all data visible

## Current Status

**Implemented:**
- Full project scaffolding with Reflex
- Service registry with lazy loading
- Database manager with DuckDB
- Market data service (yfinance)
- LLM service (Ollama + Google Gemini)
- Main layout with sidebar + assistant panel
- Research module with:
  - Quality/analyst/range cards
  - Portfolio integration (My Position card, P/L context)
  - Ticker autocomplete
- Portfolio module:
  - Positions tracking with live P/L
  - Integration with Research context
  - CRUD operations
- Assistant chat interface with tool calling

**Next Steps:**
1. **Research Enhancements:** Options chain integration, deeper analyst data, sentiment improvements.
2. **Home Page:** Phin Daily Brief, removed "Getting Started", improved quick actions.
3. **Deployment Prep:** Vercel compatibility, production config.

## Planning Documents

Detailed designs are in [Plan/](Plan/):
- `Finance Suite.md` - Main architecture and overview
- `Finance Suite - Assistant.md` - Assistant tools and conversation flows
- `Finance Suite - AI Services.md` - Service layer design
- `Finance Suite - Research Module.md` - Two trading strategies supported
- `Finance Suite - Options Module.md` - Trade logging and analysis
- `Finance Suite - Notes Module.md` - Structured note decomposition
- `Finance Suite - Portfolio Module.md` - Performance tracking
