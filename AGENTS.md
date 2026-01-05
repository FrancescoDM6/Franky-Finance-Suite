# AGENTS.md - Phinan Finance Suite Agentic Patterns

This document defines the **Architectural Patterns** and **Coding Conventions** for the Phinan Finance Suite. It serves as the source of truth for "Agentic" development—how we build intelligent, reliable, and user-centric features.

---

## 1. Core Philosophy: The Agentic Stack

An "Agent" in this codebase is not just a script; it is a composed vertical slice responsible for a specific domain (e.g., Research, Trading, Notes).

### The Three Layers of an Agent
1.  **Service Layer (`services/`)**: The "Brain". Pure logic, stateless, handles I/O and intelligence.
    *   *Rule*: Never import Reflex `rx` here. Must be runnable from CLI/Notebooks.
2.  **State Layer (`modules/*/state.py`)**: The "Memory". Manages user intent, UI state, and calls Services.
    *   *Rule*: Use `async for` generators for multi-step tasks.
3.  **UI Layer (`modules/*/components/`)**: The "Body". Reactive frontend that reflects the State.
    *   *Rule*: Dumb components. No logic, just binding.

---

## 2. AI Service Architecture

We follow the **"Right Tool for the Job"** principle. Do not default to LLMs for everything.

| Task Type | Tool | Why? |
| :--- | :--- | :--- |
| **Synthesis / Explanation** | **LLM (Ollama)** | Great at summarizing context and natural language generation. |
| **Sentiment Analysis** | **FinBERT** | 100x faster, deterministic, trained for finance. |
| **Similarity Search** | **Embeddings** | Efficient vector search for "finding similar" items. |
| **Data Extraction** | **Regex / OCR** | Precise. LLMs hallucinate numbers. |

### Service Registry Pattern
Services are lazy-loaded to keep startup fast.

```python
# services/__init__.py
from functools import cached_property

class ServiceRegistry:
    @cached_property
    def market_data(self) -> "MarketDataService":
        from .market_data import MarketDataService
        return MarketDataService()
        
    @cached_property
    def synthesis(self) -> "SynthesisService":
        from .synthesis import SynthesisService
        return SynthesisService()

services = ServiceRegistry()
```

### AI Caching Pattern (Context Hash)
AI generation is expensive. Cache aggressively based on **input context**, not just prompt.

```python
# From phinan/services/synthesis.py
def _compute_context_hash(self, context: ResearchContext) -> str:
    """Generate hash of context to invalidate cache when data changes."""
    hash_data = {
        "ticker": context.ticker,
        "price": round(context.price, 0), # Fuzzy match price
        "sentiment_hash": context.sentiment_hash,
        "user_profile": context.profile_name
    }
    return hashlib.md5(json.dumps(hash_data).encode()).hexdigest()
```

---

## 3. Reflex Agent Patterns

### The "Thinking" UI Pattern
Users need to know what the agent is doing. Use **Async Generators** (`yield`) to push updates during long tasks.

```python
# phinan/modules/research/state.py
async def evaluate_ticker(self):
    """Multi-step agent workflow."""
    
    # 1. State Update
    self.loading_stage = "Fetching Market Data..."
    yield # Pushes update to UI
    info = services.markets.get_ticker_info(self.symbol)
    
    # 2. State Update
    self.loading_stage = "Analyzing Sentiment..."
    yield
    sentiment = services.sentiment.score(info.news)
    
    # 3. Final Result
    self.result = f"{info.name}: {sentiment}"
    self.is_loading = False
```

### State Isolation Pattern
Isolate agent memory. Do not dump everything into "global" state.

```python
# Good: Specific State
class ResearchState(rx.State):
    ticker: str = ""
    results: ResearchResult = None

# Bad: Monolithic State
class State(rx.State):
    research_ticker: str = ""
    trading_ticker: str = ""
```

---

## 4. Coding Conventions

### Import Organization
1.  **Standard Lib**
2.  **Third Party** (Reflex, Pydantic, Pandas)
3.  **Local Application** (Relative imports preferred for modules)

```python
import json
from datetime import datetime

import reflex as rx
import pandas as pd

from ...services import services
from ..models import TickerInfo
```

### Lazy Imports
Heavy ML libraries (numpy, torch, transformers) MUST be imported inside methods or behind `TYPE_CHECKING` guards.

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

def calculate_volatility(self):
    import numpy as np  # Load only when needed
    ...
```

### Error Handling
- **Services**: Return `Result` objects or raise specific exceptions.
- **State**: Catch exceptions and set `self.error_message` for user feedback.

```python
# Service
def get_data(self):
    if not found:
        return None 

# State
try:
    data = service.get_data()
except Exception as e:
    self.error_message = f"Agent Error: {str(e)}"
```

---

## 5. Data Patterns (DuckDB)

### Singleton Manager
We use a singleton `DatabaseManager` with a shared connection for reads and a lock for writes.

```python
# phinan/core/database.py
with self._writer_lock:
    # Only one writer at a time
    conn.execute("INSERT ...")
```

### Migrations
Always use the migration system for schema changes.
*   File format: `migrations/001_initial_schema.sql`

---

## 6. Critical Rules for Agentic Features

1.  **Determinism**: If an agent makes a decision (e.g., "Buy"), allow the user to see *why*. Log the reasoning.
2.  **Fail Gracefully**: If the LLM service is down, the app should still work (e.g., show market data without the summary).
3.  **User in the Loop**: Critical actions (Trades, Deletions) require explicit user confirmation.
4.  **Aesthetics**: The UI should feel "alive". Use loading skeletons, progress bars, and transition animations.
