# Phinan Suite

A personal finance application with an AI assistant as the primary interface. Built with Reflex, powered by local LLM (Ollama), and featuring advanced financial analysis capabilities.

## Architecture

### Three-Layer Design

1. **Interface Layer**
   - Persistent AI Assistant (sidebar chat UI)
   - Context-aware conversations
   - Session management

2. **Tool/Data Layer**
   - Research module (market data, sentiment, volatility)
   - Notes module (semantic search, organization)
   - Portfolio module (holdings tracking, performance)
   - Options module (positions, strategies)

3. **Intelligence Layer**
   - LLM Service (Ollama integration)
   - Sentiment Service (FinBERT)
   - Volatility Service (GARCH)
   - Embedding Service (sentence-transformers)

## Project Structure

```
├── phinan/
│   ├── config.py                   # Configuration management
│   ├── rxconfig.py                 # Reflex configuration
│   │
│   ├── core/                       # Core infrastructure
│   │   ├── base_state.py          # Base state for all modules
│   │   ├── database.py            # DuckDB connection manager
│   │   ├── services.py            # Service registry pattern
│   │   └── schemas.py             # Database schema definitions
│   │
│   ├── services/                   # AI/ML services
│   │   ├── llm_service.py         # Ollama LLM integration
│   │   ├── sentiment_service.py   # FinBERT sentiment
│   │   ├── volatility_service.py  # GARCH volatility
│   │   └── embedding_service.py   # Sentence transformers
│   │
│   ├── assistant/                  # AI assistant
│   │   ├── state.py               # Assistant state management
│   │   ├── components.py          # Chat UI components
│   │   └── context_manager.py     # Context persistence
│   │
│   ├── modules/                    # Feature modules
│   │   ├── research/
│   │   ├── notes/
│   │   ├── options/
│   │   └── portfolio/
│   │
│   ├── components/                 # Shared UI components
│   │   └── layout.py              # Main layout with sidebar
│   │
│   └── pages/                      # Reflex pages
│       └── index.py               # Dashboard
│
└── migrations/                     # Database migrations
    ├── 001_initial_schema.sql
    └── migration_runner.py
```

## Setup Instructions

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running
- Git

### 2. Install Ollama and Pull Model

```bash
# Install Ollama from https://ollama.ai

# Pull the default model (llama3.2)
ollama pull llama3.2:latest

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 3. Clone and Install

```bash
cd c:\Users\frank\Documents\GitHub\Franky-Finance-Suite

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

### 4. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env to customize settings (optional)
# The defaults should work out of the box
```

### 5. Initialize Database

```bash
# Run migrations
python migrations/migration_runner.py
```

### 6. Run the Application

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

All configuration is managed via environment variables with the `PHINAN_` prefix:

### Database
- `PHINAN_DATABASE__PATH` - Path to DuckDB file (default: `~/.phinan/phinan.duckdb`)

### Ollama LLM
- `PHINAN_OLLAMA__BASE_URL` - Ollama API URL (default: `http://localhost:11434`)
- `PHINAN_OLLAMA__MODEL` - Model name (default: `llama3.2:latest`)
- `PHINAN_OLLAMA__TIMEOUT` - Request timeout in seconds (default: `120`)

### AI Services
- `PHINAN_AI_SERVICES__SENTIMENT_MODEL` - FinBERT model (default: `yiyanghkust/finbert-tone`)
- `PHINAN_AI_SERVICES__EMBEDDING_MODEL` - Embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `PHINAN_AI_SERVICES__ENABLE_SENTIMENT` - Enable sentiment service (default: `true`)
- `PHINAN_AI_SERVICES__ENABLE_VOLATILITY` - Enable volatility service (default: `true`)
- `PHINAN_AI_SERVICES__ENABLE_EMBEDDINGS` - Enable embeddings service (default: `true`)

## Key Design Patterns

### 1. State Management

All module states inherit from `BaseState`, which provides:
- Access to service registry via `self.services`
- Database manager via `self.db`
- Configuration via `self.config`
- Common error handling methods

Example:
```python
from phinan.core.base_state import BaseState

class ResearchState(BaseState):
    ticker: str = ""

    async def analyze_ticker(self):
        # Access LLM service
        response = await self.services.llm_service.chat(...)

        # Access database
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO research ...")
```

### 2. Service Registry Pattern

Services are lazy-loaded on first access:

```python
from phinan.core.services import get_service_registry

services = get_service_registry()

# Service loaded only when accessed
sentiment = services.sentiment_service.analyze_sentiment("Great earnings!")
```

### 3. Database Connections

DuckDB connections are per-request using context managers:

```python
with self.db.get_connection() as conn:
    results = conn.execute("SELECT * FROM portfolio").fetchall()
# Connection automatically closed
```

### 4. Layout Pattern

All pages use the `main_layout` wrapper for consistent structure:

```python
from phinan.components.layout import main_layout

def my_page():
    return main_layout(
        rx.heading("My Page"),
        rx.text("Content")
    )
```

## Development Workflow

### Adding a New Module

1. Create module directory in `phinan/modules/`
2. Create `state.py` inheriting from `BaseState`
3. Create `page.py` with Reflex components
4. Create `tools.py` for module-specific logic
5. Import page in `phinan/pages/__init__.py`

### Adding a New Service

1. Create service class in `phinan/services/`
2. Add `@cached_property` in `ServiceRegistry` (core/services.py)
3. Access via `self.services.your_service` in states

### Adding Database Tables

1. Create migration SQL in `migrations/NNN_description.sql`
2. Run `python migrations/migration_runner.py`
3. Update `core/schemas.py` with schema documentation

## Next Steps

1. Implement module pages (research, notes, portfolio, options)
2. Add yfinance integration for market data
3. Implement semantic search in notes module
4. Add portfolio performance tracking
5. Build options strategy analyzer
6. Implement context-aware assistant tools

## Troubleshooting

### Ollama Not Connecting
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

## License

Private project - All rights reserved
