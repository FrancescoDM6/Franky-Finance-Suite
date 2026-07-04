# Phinan Finance Suite - Developer Guide

This document covers setup, configuration, the development workflow, and
deployment. For a high-level overview see [README.md](README.md). For
architectural patterns and coding conventions see [AGENTS.md](AGENTS.md).

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Configuration Reference](#configuration-reference)
- [Development Workflow](#development-workflow)
- [User Profiles](#user-profiles)
- [Implementation Status](#implementation-status)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Architecture

The codebase is organized as vertical "agent" slices over a shared service
layer. There are three layers (described in detail in [AGENTS.md](AGENTS.md)):

1. **Service layer (`phinan/services/`)** - stateless logic and I/O (market data,
   LLM, sentiment, volatility, embeddings). Never imports Reflex.
2. **State layer (`phinan/modules/*/state.py`, `phinan/state/`)** - manages UI
   state and orchestrates service calls.
3. **UI layer (`phinan/modules/*/components/`, `phinan/components/`)** - reactive
   Reflex components that bind to state.

Services are lazy-loaded through a registry (`phinan/services/__init__.py`) so
startup stays fast and heavy ML dependencies load only when first used.

## Project Structure

```
├── rxconfig.py                 # Reflex configuration (root)
├── migrations/                 # DuckDB migrations + runner
│   ├── 001_initial_schema.sql
│   ├── 002_optimize_market_cache.sql
│   ├── 003_optimize_options.sql
│   └── migration_runner.py
├── phinan/
│   ├── phinan.py               # Main app entry
│   ├── api/                    # FastAPI health/metrics endpoints
│   │   └── health.py
│   ├── config/
│   │   └── settings.py         # Pydantic settings (PHINAN_ env prefix)
│   ├── core/                   # Database, metrics, async + memory utils
│   │   └── database.py         # DuckDB connection manager
│   ├── services/               # Lazy-loaded service registry
│   │   ├── __init__.py         # ServiceRegistry
│   │   ├── llm.py              # Gemini + Ollama
│   │   ├── market_data.py      # OpenBB + yfinance adapter
│   │   ├── sentiment.py        # FinBERT
│   │   ├── volatility.py       # GARCH
│   │   └── embeddings.py       # sentence-transformers
│   ├── state/
│   │   ├── app.py              # Global app state
│   │   └── user_context.py     # User preferences & profiles
│   ├── components/             # Shared UI
│   │   ├── layout.py           # Main layout wrapper
│   │   ├── sidebar.py          # Navigation sidebar
│   │   └── ui.py               # Reusable UI helpers
│   ├── modules/
│   │   ├── research/           # Research page, state, profiles, cards
│   │   ├── portfolio/          # Portfolio tracking page + state
│   │   ├── notes/              # Stub
│   │   └── options/            # Stub
│   └── pages/
│       ├── index.py            # Home dashboard + Daily Brief
│       └── settings.py         # Settings page
└── tests/                      # unit / integration / e2e / performance
```

## Setup

### Prerequisites

- Python 3.10+
- Git
- A Google Gemini API key (recommended) **or** [Ollama](https://ollama.ai) running locally

### Install

```bash
git clone https://github.com/FrancescoDM6/Franky-Finance-Suite.git
cd Franky-Finance-Suite

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
# For development (tests, linting):
pip install -r requirements-dev.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env - at minimum set PHINAN_GEMINI_API_KEY, or configure Ollama.
```

**Gemini (recommended):**

```bash
PHINAN_GEMINI_API_KEY=your_api_key_here   # https://aistudio.google.com/app/apikey
```

**Ollama (local fallback):** used automatically when no Gemini key is set.

```bash
ollama pull llama3.2:latest
curl http://localhost:11434/api/tags      # verify it is running
```

### Initialize the database and run

```bash
python migrations/migration_runner.py
reflex run
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Configuration Reference

All settings use the `PHINAN_` prefix and are defined in
`phinan/config/settings.py`. Nested settings use a double underscore
(e.g. `PHINAN_DATABASE__PATH`). Defaults below reflect the actual code.

### Application
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PHINAN_DEBUG` | `false` | Debug mode |
| `PHINAN_DATABASE__PATH` | `./data/phinan.duckdb` | DuckDB file path (use `/data/phinan.duckdb` on Railway with a volume) |

### Gemini LLM (primary)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PHINAN_GEMINI_API_KEY` | _(empty)_ | Required to use Gemini |
| `PHINAN_GEMINI_MODEL` | `gemini-3.1-flash-lite` | Model name |

### Ollama LLM (fallback)
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PHINAN_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `PHINAN_OLLAMA_MODEL` | `llama3.2:latest` | Model name |
| `PHINAN_OLLAMA_TIMEOUT` | `120` | Request timeout (seconds) |

### AI services
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PHINAN_AI_SERVICES_SENTIMENT_MODEL` | `ProsusAI/finbert` | FinBERT sentiment model |
| `PHINAN_AI_SERVICES_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `PHINAN_AI_SERVICES_ENABLE_SENTIMENT` | `false` | Enable sentiment service |
| `PHINAN_AI_SERVICES_ENABLE_VOLATILITY` | `false` | Enable GARCH volatility |
| `PHINAN_AI_SERVICES_ENABLE_EMBEDDINGS` | `false` | Enable embeddings |

> AI services are disabled by default to keep startup fast. Enable them
> individually as needed.

### Market data
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PHINAN_MARKET_DATA_PROVIDER` | `openbb` | Primary provider (`openbb` or `yfinance`) |
| `PHINAN_MARKET_DATA_OPENBB_PROVIDER` | `yfinance` | OpenBB backend (`yfinance`, `fmp`, `polygon`, ...) |
| `PHINAN_MARKET_DATA_CACHE_TTL_MINUTES` | `5` | Cache TTL for market data |
| `PHINAN_MARKET_DATA_RATE_LIMIT_DELAY` | `0.5` | Delay between API calls (seconds) |

## Development Workflow

> Patterns referenced below (service registry, "thinking" UI generators, state
> isolation, the "right tool for the job" rule) are documented in
> [AGENTS.md](AGENTS.md). This section covers the mechanical steps.

### Add a module

1. Create `phinan/modules/<name>/`.
2. Add `state.py` extending `rx.State`.
3. Add `page.py` with Reflex components, wrapped in `main_layout`.
4. Access services via `from phinan.services import services`.
5. Register the page in `phinan/pages/__init__.py` (or the module's `__init__`).

### Add a service

1. Create `phinan/services/<name>.py`.
2. Add a `@cached_property` for it in `ServiceRegistry`
   (`phinan/services/__init__.py`).
3. Use it anywhere via `services.<name>`.

### Add a database table

1. Create `migrations/NNN_description.sql`.
2. Run `python migrations/migration_runner.py`.
3. Access via `services.db`.

### Run tests

```bash
pytest                       # full suite
pytest tests/unit            # unit only
```

## User Profiles

Three research profiles emphasize different metrics and option timeframes:

- **Papi** - conservative, ~2-week options, dividend-yield focus.
- **Tio** - aggressive, 1-2 month plays, momentum focus.
- **Franky** - learning mode, all data visible.

Profiles affect default option expirations shown, generated insights, and which
metrics the UI emphasizes.

## Implementation Status

**Functional**
- Service registry with lazy loading
- DuckDB manager and migrations
- Market data service (OpenBB primary, yfinance fallback)
- LLM service (Gemini with Ollama fallback)
- Research module (quality/analyst/range/news/options cards, sentiment,
  profile-aware insights, LLM synthesis)
- Portfolio module (positions, live P/L, gainers/losers, research integration)
- Home dashboard with the LLM Daily Brief

**Implemented but inactive (disabled by default)**
- Sentiment service (FinBERT)
- Volatility service (GARCH)
- Embeddings service (sentence-transformers)

**Planned / stubs**
- Persistent chat assistant (not started)
- Notes module
- Options module (beyond the research options card)

## Deployment

The project targets Railway using a split frontend/backend container.

- **Frontend:** Caddy serves the pre-compiled static React app and reverse-proxies
  API requests (listens on `$PORT`).
- **Backend:** `scripts/start.py` runs migrations, then starts the backend via
  `reflex run --backend-only --env prod` on port 8000. This properly initializes
  the Reflex runtime without re-compiling the frontend at startup.
- **State:** Redis (persistent) when `REDIS_URL` is set; otherwise disk.

### Production environment variables
| Variable | Description |
| :--- | :--- |
| `API_URL` | Public URL of the deployment (e.g. `https://yourapp.up.railway.app`) |
| `REDIS_URL` | Redis connection string (enables Redis state manager) |

The Docker build compiles frontend assets (`reflex export`), then the runtime
serves them via Caddy while `start.py` handles the backend. See `Dockerfile`,
`Caddyfile`, `scripts/start.py`, and `docker-compose.yml`.

### Database backups

All persistent data lives in a single DuckDB file (`/data/phinan.duckdb` on
Railway, `./data/phinan.duckdb` locally). There is no automatic backup, so
back it up before risky changes and periodically in production:

- **Railway:** attach the `/data` volume and use volume snapshots, or run a
  one-off shell and copy the file out (`railway ssh` / `railway run`).
- **Manual export (portable across DuckDB versions):**
  ```sql
  -- duckdb /data/phinan.duckdb
  EXPORT DATABASE '/data/backup_2026_07_04' (FORMAT PARQUET);
  ```
- **Local:** copy the file while the app is stopped (DuckDB holds an
  exclusive write lock while the backend runs).

## Troubleshooting

### LLM not connecting

**Gemini:** confirm `PHINAN_GEMINI_API_KEY` is set in `.env` and has quota.

**Ollama:**
```bash
curl http://localhost:11434/api/tags   # check it is running
ollama serve                           # start it
```

### Module import errors

```bash
pip install -e .
```

### Database issues

```bash
# WARNING: destroys all data
rm ./data/phinan.duckdb
python migrations/migration_runner.py
```

### Reflex build errors

```bash
rm -rf .web
reflex init
reflex run
```
