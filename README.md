# Phinan Finance Suite

A personal finance application with an AI assistant as the primary interface. Built with Reflex, powered by Google Gemini (with local Ollama fallback), and featuring advanced financial analysis capabilities.

> **Project Status:** Prototype / Active Development
>
> Core modules (Research, Portfolio) are functional. AI assistant integration is active. UI is being refined.

## Architecture

### Three-Layer Design

1. **Interface Layer**
   - Persistent AI Assistant (sidebar chat UI)
   - Context-aware conversations with tool calling
   - Session management

2. **Tool/Data Layer**
   - Research module (market data, sentiment, volatility, options analysis)
   - Portfolio module (holdings tracking, performance, P/L)
   - Notes module (planned - semantic search, organization)
   - Options module (planned - positions, strategies)

3. **Intelligence Layer**
   - LLM Service (Google Gemini with Ollama fallback)
   - Sentiment Service (FinBERT)
   - Volatility Service (GARCH - planned)
   - Embedding Service (sentence-transformers - planned)

## Project Structure

```
├── rxconfig.py                 # Reflex configuration (root)
├── phinan/
│   ├── phinan.py               # Main app entry
│   ├── config/
│   │   └── settings.py         # Pydantic settings with env vars
│   │
│   ├── core/
│   │   └── database.py         # DuckDB connection manager
│   │
│   ├── services/               # AI/ML services registry
│   │   ├── __init__.py         # ServiceRegistry (lazy-loaded)
│   │   ├── llm.py              # Gemini + Ollama LLM
│   │   ├── sentiment.py        # FinBERT sentiment
│   │   ├── market_data.py      # Market data (yfinance)
│   │   ├── volatility.py       # GARCH volatility (stub)
│   │   └── embeddings.py       # Sentence transformers (stub)
│   │
│   ├── state/
│   │   ├── app.py              # Global app state
│   │   └── user_context.py     # User preferences & profiles
│   │
│   ├── components/             # Shared UI components
│   │   ├── assistant/          # AI assistant chat components
│   │   ├── layout.py           # Main layout with sidebar
│   │   ├── sidebar.py          # Navigation sidebar
│   │   └── navbar.py           # Top navigation
│   │
│   ├── modules/                # Feature modules
│   │   ├── research/           # Research page with cards
│   │   │   ├── state.py        # ResearchState (extends rx.State)
│   │   │   ├── page.py         # Research UI
│   │   │   ├── profiles.py     # User profiles (Papi/Tio/Franky)
│   │   │   ├── prompts.py      # LLM prompt templates
│   │   │   └── components/     # Quality, analyst, news, options cards
│   │   │
│   │   ├── portfolio/          # Portfolio tracking
│   │   │   ├── state.py        # PortfolioState (extends rx.State)
│   │   │   └── page.py         # Portfolio UI
│   │   │
│   │   ├── notes/              # (Stub - not implemented)
│   │   └── options/            # (Stub - not implemented)
│   │
│   └── pages/                  # Reflex pages
│       ├── index.py            # Home dashboard
│       └── settings.py         # Settings page
│
└── migrations/                 # Database migrations
    ├── 001_initial_schema.sql
    └── migration_runner.py
```

## Setup Instructions

### 1. Prerequisites

- Python 3.10+
- Git
- (Optional) [Ollama](https://ollama.ai) for local LLM fallback
- Google Gemini API key (recommended) OR Ollama running locally

### 2. Clone and Install

```bash
# Clone the repository
git clone https://github.com/FrancescoDM6/Franky-Finance-Suite.git
cd Franky-Finance-Suite

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Unix/MacOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env to add your Gemini API key (recommended)
# Or configure Ollama settings if using local LLM
```

**Recommended LLM Setup (Gemini):**
Add your Google Gemini API key to `.env`:
```bash
PHINAN_GEMINI_API_KEY=your_api_key_here
PHINAN_GEMINI_MODEL=gemini-2.0-flash-exp  # or gemini-1.5-flash
```

**Alternative LLM Setup (Ollama - Local):**
If you prefer local inference or don't have a Gemini key:
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.2:latest

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 4. Initialize Database

```bash
# Run migrations
python migrations/migration_runner.py
```

### 5. Run the Application

```bash
# Initialize Reflex (first time only)
reflex init

# Start the development server
reflex run
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Configuration Options

All configuration is managed via environment variables with the `PHINAN_` prefix.

### Database
- `PHINAN_DATABASE__PATH` - Path to DuckDB file (default: `~/.phinan/phinan.duckdb`; use `/data/phinan.duckdb` in Docker)

### Google Gemini LLM (Primary)
- `PHINAN_GEMINI_API_KEY` - Google Gemini API key (required for Gemini)
- `PHINAN_GEMINI_MODEL` - Model name (default: `gemini-2.0-flash-exp`)
- `PHINAN_GEMINI_TIMEOUT` - Request timeout in seconds (default: `60`)

### Ollama LLM (Fallback)
- `PHINAN_OLLAMA_BASE_URL` - Ollama API URL (default: `http://localhost:11434`)
- `PHINAN_OLLAMA_MODEL` - Model name (default: `llama3.2:latest`)
- `PHINAN_OLLAMA_TIMEOUT` - Request timeout in seconds (default: `120`)

### AI Services
- `PHINAN_AI_SERVICES_SENTIMENT_MODEL` - FinBERT model (default: `yiyanghkust/finbert-tone`)
- `PHINAN_AI_SERVICES_EMBEDDING_MODEL` - Embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `PHINAN_AI_SERVICES_ENABLE_SENTIMENT` - Enable sentiment service (default: `false`)
- `PHINAN_AI_SERVICES_ENABLE_VOLATILITY` - Enable volatility service (default: `false`)
- `PHINAN_AI_SERVICES_ENABLE_EMBEDDINGS` - Enable embeddings service (default: `false`)

### Market Data
- `PHINAN_MARKET_DATA_PROVIDER` - Data provider (default: `yfinance`)
- `PHINAN_MARKET_DATA_CACHE_TTL_MINUTES` - Cache TTL (default: `5`)

## Key Design Patterns

### 1. State Management

Module states extend `rx.State` directly (Reflex's base state class):

```python
import reflex as rx

class ResearchState(rx.State):
    ticker: str = ""
    ticker_info: dict[str, Any] = {}

    async def research_ticker(self):
        # Access services via global registry
        from phinan.services import services

        # Call service methods
        info = services.market_data.get_ticker_info(self.ticker)
        self.ticker_info = info
```

### 2. Service Registry Pattern

Services are lazy-loaded on first access via a global registry:

```python
from phinan.services import services

# Services loaded only when accessed
response = services.llm.complete("Analyze this stock...")
info = services.market_data.get_ticker_info("AAPL")
positions = services.db.query("SELECT * FROM portfolio")
```

The registry uses `@cached_property` to ensure each service is initialized only once per application lifecycle.

### 3. Database Connections

DuckDB connections are managed via context managers:

```python
from phinan.services import services

# Get database connection
conn = services.db.get_connection()
results = conn.execute("SELECT * FROM portfolio").fetchall()
# Connection automatically managed by service
```

### 4. Layout Pattern

All pages use the `main_layout` wrapper for consistent structure:

```python
from phinan.components.layout import main_layout
import reflex as rx

def my_page():
    return main_layout(
        rx.heading("My Page"),
        rx.text("Content")
    )
```

### 5. LLM Service Pattern

The LLM service prioritizes Google Gemini (cloud) with automatic fallback to Ollama (local):

```python
from phinan.services import services

# Health check (returns True if any LLM available)
if services.llm.health_check():
    # Single completion
    response = services.llm.complete("What is Python?")

    # Multi-turn chat
    messages = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "Tell me about stocks"}
    ]
    response = services.llm.chat(messages)
```

If `PHINAN_GEMINI_API_KEY` is set, Gemini is used. Otherwise, the service falls back to Ollama.

## Development Workflow

### Adding a New Module

1. Create module directory in `phinan/modules/`
2. Create `state.py` extending `rx.State`
3. Create `page.py` with Reflex components
4. Access services via `from phinan.services import services`
5. Import page in `phinan/pages/__init__.py`

Example:
```python
# phinan/modules/mymodule/state.py
import reflex as rx
from phinan.services import services

class MyModuleState(rx.State):
    data: str = ""

    async def load_data(self):
        # Access services
        result = services.market_data.get_ticker_info("AAPL")
        self.data = result
```

### Adding a New Service

1. Create service class in `phinan/services/your_service.py`
2. Add `@cached_property` in `ServiceRegistry` (`phinan/services/__init__.py`)
3. Access via `services.your_service` anywhere in the codebase

Example:
```python
# phinan/services/my_service.py
class MyService:
    def do_something(self):
        return "result"

# phinan/services/__init__.py
class ServiceRegistry:
    @cached_property
    def my_service(self) -> MyService:
        from .my_service import MyService
        return MyService()
```

### Adding Database Tables

1. Create migration SQL in `migrations/NNN_description.sql`
2. Run `python migrations/migration_runner.py`
3. Access via `services.db` in your state classes

## User Profiles

Three trading profiles with different research emphasis:
- **Papi:** Conservative, 2-week options, dividend yield focus
- **Tio:** Aggressive, 1-2 month plays, momentum focus
- **Franky:** Learning mode, all data visible

Profiles affect:
- Default options expirations shown in research
- Insights and recommendations generated by the assistant
- Which metrics are emphasized in the UI

## Current Implementation Status

### Fully Implemented
- Project scaffolding with Reflex
- Service registry with lazy loading
- Database manager with DuckDB
- Market data service (yfinance adapter)
- LLM service (Google Gemini with Ollama fallback)
- Main layout with sidebar and persistent assistant panel
- Research module:
  - Ticker search with autocomplete
  - Quality/analyst/range/news/options cards
  - Portfolio integration (P/L context if ticker is owned)
  - Profile-aware insights and LLM synthesis
  - FinBERT sentiment analysis for news
- Portfolio module:
  - Position tracking with live P/L calculations
  - Add/edit/delete positions
  - Integration with Research module
- Assistant chat interface:
  - Multi-turn conversations with context
  - Tool calling capability (planned expansion)

### Partially Implemented / Stubs
- Volatility service (GARCH) - defined but not used
- Embeddings service - defined but not used
- Notes module - stub only
- Options module - stub only

### Planned Features
1. **Research Enhancements:**
   - Expanded options chain analysis
   - Historical analyst data trends
   - Enhanced sentiment granularity

2. **Home Page:**
   - "Phin Daily Brief" with portfolio commentary
   - Personalized quick actions
   - Portfolio performance summary

3. **Deployment:**
   - **Platform:** Railway
   - **Architecture:** Docker (Split Frontend/Backend with Caddy)
   - **State Management:** Redis (Persistent)

## Production Configuration

The project is optimized for deployment on Railway:

### Environment Variables
- `API_URL`: Public URL of your Railway app (e.g., `https://yourapp.up.railway.app`)
- `REDIS_URL`: Connection string for Redis service
- `REFLEX_ENV`: Set to `prod` automatically by setup

### Docker Optimization
1.  **Build Stage:** Compiles frontend assets (`reflex export`).
2.  **Runtime:** 
    - Runs `caddy` to serve the static frontend and proxy API requests.
    - Runs `uvicorn` directly for the backend (skipping runtime compilation).

## Troubleshooting

### LLM Not Connecting

**For Gemini:**
```bash
# Verify API key is set in .env
# Check that key is valid and has quota remaining
```

**For Ollama:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama service
ollama serve
```

### Module Import Errors
```bash
# Reinstall in development mode
pip install -e .
```

### Database Issues
```bash
# Reset database (WARNING: destroys all data)
rm ~/.phinan/phinan.duckdb
python migrations/migration_runner.py
```

### Reflex Build Errors
```bash
# Clear Reflex cache and rebuild
rm -rf .web
reflex init
reflex run
```

## License

Private project - All rights reserved
