# Phinan Finance Suite

A personal finance application for investment research and portfolio tracking,
built with [Reflex](https://reflex.dev) (Python that compiles to React). It pairs
live market data with AI-assisted synthesis to help you research tickers and
follow your holdings.

> **Status:** Prototype / active development. The Research and Portfolio modules
> are functional. A persistent chat assistant, Notes, and Options modules are
> planned (see [Roadmap](#roadmap)).

## Features

- **Research module** - ticker lookup with autocomplete, quality/analyst/range
  cards, news with FinBERT sentiment, options chain view, and GARCH volatility.
- **Portfolio module** - position tracking with live P/L, gainers/losers, and
  research integration (P/L context when you look up a ticker you own).
- **Daily Brief** - an LLM-generated summary of your portfolio and watchlist on
  the home dashboard.
- **Profile-aware insights** - three research profiles (Papi / Tio / Franky) that
  emphasize different metrics and option timeframes.

## Tech Stack

| Concern | Tool |
| :--- | :--- |
| UI framework | Reflex (Python -> React) |
| LLM | Google Gemini (cloud) with Ollama (local) fallback |
| Market data | OpenBB / yfinance (adapter pattern) |
| Database | DuckDB (embedded) |
| Sentiment | FinBERT |
| Volatility | GARCH via `arch` |
| Charts | Plotly |

## Quickstart

```bash
# 1. Clone and enter
git clone https://github.com/FrancescoDM6/Franky-Finance-Suite.git
cd Franky-Finance-Suite

# 2. Create a virtual environment and install
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env and set PHINAN_GEMINI_API_KEY (recommended),
# or run Ollama locally for the fallback. See README-dev.md for all options.

# 4. Initialize the database
python migrations/migration_runner.py

# 5. Run
reflex run
```

The app serves the frontend at http://localhost:3000 and the backend at
http://localhost:8000.

> Don't have a Gemini key? Install [Ollama](https://ollama.ai), run
> `ollama pull llama3.2:latest`, and the LLM service falls back to it automatically.

## Documentation

- **[README-dev.md](README-dev.md)** - full setup, configuration reference,
  development workflow, troubleshooting, and deployment.
- **[AGENTS.md](AGENTS.md)** - architectural patterns and coding conventions.
- **[CLAUDE.md](CLAUDE.md)** - guidance for AI coding agents working in this repo.

## Roadmap

- Persistent chat assistant as the primary interface (tool calling over the
  modules below).
- Notes module - structured note decomposition and semantic search.
- Options module - trade logging and strategy analysis.

## License

Private project - all rights reserved.
