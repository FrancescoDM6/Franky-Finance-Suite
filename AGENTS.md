# AGENTS.md - Phinan Finance Suite Coding Conventions

This file documents the **actual** coding patterns and conventions used in Phinan Finance Suite codebase. Follow these patterns when working with agentic coding assistants to maintain consistency.

## Import Organization Patterns

### Standard Import Order
1. **Standard library imports** (alphabetical)
2. **Third-party imports** (alphabetical) 
3. **Local imports** (relative imports, alphabetical)

### Import Style Examples

```python
# Standard library imports
import json
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Protocol, Union, TYPE_CHECKING
from zoneinfo import ZoneInfo

# Third-party imports
import duckdb
import pandas as pd
import reflex as rx
from dataclasses import dataclass
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local imports
from ..config.settings import settings
from ..core.database import get_database_manager
from ..models.volatility import GARCHForecast, ExpectedRange, VolatilityComparison
```

### Lazy Import Patterns
Heavy dependencies are imported lazily inside functions to reduce startup memory:

```python
# Lazy imports for heavy dependencies (numpy, pandas, scipy)
# These are only loaded when the service is actually used
if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

def process_data(self):
    try:
        import numpy as np  # Imported inside function
        # ... use numpy
    except ImportError:
        return {"error": "numpy not installed"}
```

### Conditional Import Pattern
For optional dependencies or platform-specific code:

```python
def _get_model(self):
    if self._model is None:
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            # Initialize model
        except ImportError:
            raise ImportError("transformers not installed. Run: pip install transformers")
    return self._model
```

## Error Handling Patterns

### Service Layer Pattern
Services return structured results - either dataclasses or error dicts:

```python
def forecast(self, returns: pd.Series, horizon: int = 5) -> Union[GARCHForecast, dict]:
    """Forecast volatility using GARCH(1,1)."""
    if not self._enabled:
        return {"error": "Volatility service disabled", "enabled": False}
    
    try:
        # ... computation
        return GARCHForecast(...)  # Success case
    except ImportError:
        return {"error": "arch package not installed. Run: pip install arch"}
    except Exception as e:
        return {"error": str(e)}
```

### Silent Fail with Logging
For non-critical operations (caching, optional features):

```python
def _get_cached_data(self, symbol: str, data_type: str) -> Optional[dict]:
    try:
        # Cache lookup logic
        pass
    except Exception as e:
        # Silent fail on cache error to fallback to live data
        print(f"Cache read error for {symbol}: {e}")
    return None
```

### Health Check Pattern
All services implement a health check method:

```python
def health_check(self) -> bool:
    """Check if service is available."""
    try:
        # Quick connectivity/availability test
        import yfinance
        return True
    except Exception:
        return False
```

## Type Hints Usage

### Function Signatures
Comprehensive type hints with Union types for error handling:

```python
def compare_to_implied_vol(
    self,
    current_price: float,
    returns: pd.Series,
    implied_vol: float,
    horizon: int = 21,
    confidence: float = 0.68,
) -> Union[VolatilityComparison, dict]:
    """Compare GARCH forecast to implied volatility."""
```

### Class Attributes
Type hints for all public attributes:

```python
class ResearchState(rx.State):
    ticker_input: str = ""
    selected_ticker: str = ""
    is_loading: bool = False
    ticker_info: dict[str, Any] = {}
    recent_news: list[NewsItem] = []
```

### Protocol Usage
For dependency injection and interface definitions:

```python
class LLMSentimentProvider(Protocol):
    """Protocol for LLM-based sentiment scoring."""
    
    def score_sentiment(self, text: str) -> dict:
        """Score sentiment using LLM."""
        ...
```

## Naming Conventions

### Classes
PascalCase with descriptive names:

```python
class MarketDataService:
class DatabaseManager:
class LRUCache:
class VolatilityComparison:
class Settings(BaseSettings):
```

### Methods and Functions
snake_case with descriptive verbs:

```python
def get_ticker_info(self, symbol: str) -> Optional[TickerInfo]:
def _get_cached_data(self, symbol: str, data_type: str) -> Optional[dict]:
def health_check(self) -> bool:
def compare_to_implied_vol(self, ...) -> Union[VolatilityComparison, dict]:
```

### Variables
snake_case with descriptive names:

```python
selected_expiration: str = ""
volatility_garch_vol: float = 0.0
options_atm_iv: float = 0.0
cache_key: str = f"{ticker}:{expiration}"
```

### Constants
UPPER_SNAKE_CASE for module-level constants:

```python
CONFIDENCE_THRESHOLD = 0.8
OPTIONS_CACHE_TTL = 300
OPTIONS_CACHE_MAX_SIZE = 100
FORECAST_HORIZONS = [
    {"value": "5", "label": "1 Week (5 days)"},
    {"value": "21", "label": "1 Month (21 days)"},
]
```

### Private Members
Single underscore prefix for internal use:

```python
def _load_model(self):
def _get_shared_connection(self):
self._initialized: bool = False
self._cache: OrderedDict[str, dict] = OrderedDict()
```

## Code Formatting Style

### Line Length
Generally 88-100 characters, but flexible for readability.

### String Formatting
Use f-strings for string interpolation:

```python
cache_key = f"{self.selected_ticker}:{self.selected_expiration}"
error_msg = f"Error fetching options: {str(e)}"
return f"{self.volatility_implied_vol * 100:.1f}%"
```

### Dictionary Construction
Multi-line for complex dictionaries:

```python
self.analyst_data = {
    "rating": info.analyst_rating,
    "target_price": info.target_price,
    "num_analysts": info.num_analysts,
    "recommendation_counts": {},
    "price_targets": {},
    "recent_changes": [],
}
```

### Method Chaining
Break chains across lines for readability:

```python
history_data = []
for idx, row in df.iterrows():
    history_data.append({
        "date": idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx),
        "open": round(float(row["Open"]), 2),
        "high": round(float(row["High"]), 2),
    })
```

## Testing Patterns

### Test File Naming
Test files named with `test_` prefix:
- `test_query_performance.py`
- Location: In `migrations/` directory for integration tests

### Test Structure
Simple functions for specific test scenarios:

```python
def test_portfolio_queries(db):
    """Test all portfolio-related queries."""
    print_section("Portfolio Query Performance Analysis")
    
    results = []
    
    # Query 1: Load all positions
    results.append(explain_query(
        db,
        "SELECT id, ticker_symbol, quantity, cost_basis FROM portfolio ORDER BY ticker_symbol",
        label="Load All Positions (Most Frequent)"
    ))
    
    return results
```

### Performance Testing
Use `EXPLAIN ANALYZE` for database performance testing:

```python
def explain_query(db, query: str, params: tuple = (), label: str = "") -> dict[str, Any]:
    explain_query = f"EXPLAIN ANALYZE {query}"
    start = time.perf_counter()
    result = db.query(explain_query, params)
    elapsed = (time.perf_counter() - start) * 1000
    return {"label": label, "elapsed_ms": elapsed, "success": True}
```

## Documentation Patterns

### Module Docstrings
Explain purpose and key patterns at module level:

```python
"""Market data service abstracting yfinance (swappable to Polygon).

Design pattern: Data Provider Adapter
yfinance breaks often - interface is stable, implementation swappable.
"""
```

### Class Docstrings
Describe purpose and key responsibilities:

```python
class DatabaseManager:
    """T
