# Testing Guide for Phinan Finance Suite

This document provides standardized testing patterns and guidelines for the Phinan Finance Suite. Agents and developers should follow these conventions when writing tests or diagnosing issues.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=phinan --cov-report=html

# Run specific test file
pytest tests/unit/test_services/test_llm.py -v

# Run tests matching a pattern
pytest -k "test_circuit_breaker" -v
```

## Test Structure

```
tests/
    conftest.py                 # Shared fixtures and pytest configuration
    fixtures/
        db_fixtures.py          # Database test fixtures
        api_fixtures.py         # API mock fixtures
    unit/
        test_services/          # Service layer tests
            test_llm.py
            test_market_data.py
            test_circuit_breaker.py
            test_cache_service.py
        test_core/
            test_database.py
        test_modules/
            test_research_state.py
            test_portfolio_state.py
    integration/
        test_database/
    e2e/
    performance/
```

## Test Markers

Use pytest markers to categorize tests:

| Marker | Description | Example |
|--------|-------------|---------|
| `@pytest.mark.unit` | Fast tests with no external deps | Service logic tests |
| `@pytest.mark.integration` | Tests with mocked external APIs | Database queries |
| `@pytest.mark.e2e` | End-to-end workflow tests | Full research flow |
| `@pytest.mark.slow` | Slow tests to skip in CI | Performance benchmarks |

## Testing Patterns

### 1. Service Layer Tests (Unit)

Test services in isolation by mocking all external dependencies.

```python
from unittest.mock import MagicMock, patch

@pytest.fixture
def llm_service():
    with patch("phinan.services.llm.settings") as mock_settings:
        mock_settings.gemini.api_key = "test-key"
        from phinan.services.llm import LLMService
        yield LLMService()

def test_llm_fallback_on_rate_limit(llm_service):
    # Given: Gemini returns rate limit error
    llm_service._gemini_client = MagicMock()
    llm_service._gemini_client.models.generate_content.side_effect = Exception("429")
    
    # And: Ollama is available
    llm_service._ollama_client = MagicMock()
    llm_service._ollama_client.chat.return_value = {"message": {"content": "fallback"}}
    
    # When: Chat is called
    result = llm_service.chat([{"role": "user", "content": "Hello"}])
    
    # Then: Falls back to Ollama
    assert result["content"] == "fallback"
```

### 2. Database Tests

Use in-memory DuckDB for fast, isolated database tests.

```python
from tests.fixtures.db_fixtures import in_memory_db

def test_portfolio_query(in_memory_db):
    # Given: Portfolio with positions
    in_memory_db.execute("""
        INSERT INTO portfolio (id, ticker_symbol, quantity, cost_basis)
        VALUES (1, 'AAPL', 100, 150.00)
    """)
    
    # When: Query positions
    result = in_memory_db.execute("SELECT * FROM portfolio").fetchall()
    
    # Then: Returns position
    assert len(result) == 1
    assert result[0][1] == 'AAPL'
```

### 3. Mocking External APIs

Never call real APIs in unit tests. Use fixtures from `api_fixtures.py`.

```python
def test_market_data_parsing(mock_yfinance_ticker_info):
    provider = YFinanceProvider()
    
    with patch.object(provider, "_get_yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = mock_yfinance_ticker_info
        mock_yf.return_value.Ticker.return_value = mock_ticker
        
        result = provider.get_ticker_info("AAPL")
    
    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
```

### 4. Testing Async Generators (State Layer)

For Reflex state methods that use `async for` and `yield`:

```python
@pytest.mark.asyncio
async def test_research_state_progressive_updates():
    state = ResearchState()
    state.ticker_input = "AAPL"
    
    # Mock services
    with patch("phinan.services.services") as mock_services:
        mock_services.market_data.get_ticker_info.return_value = TickerInfo(...)
        
        # Collect progressive updates
        updates = []
        async for _ in state.research_ticker():
            updates.append(state.loading_stage)
        
        # Verify sequence
        assert any("Fetching" in u for u in updates)
        assert any("Analyzing" in u for u in updates)
```

### 5. Testing Cache TTL with Freezegun

```python
from freezegun import freeze_time

@freeze_time("2024-01-01 10:00:00")
def test_cache_expires_after_ttl(cache_service):
    cache_service.set("AAPL", "ticker_info", {"price": 150})
    
    # Move time forward past TTL
    with freeze_time("2024-01-01 10:06:00"):
        result = cache_service.get("AAPL", "ticker_info")
    
    assert result is None  # Cache expired
```

## Writing New Tests

When adding tests for new features:

1. **Identify the layer**: Service (unit), State (integration), or Workflow (e2e)
2. **Mock external dependencies**: Never call real APIs/DBs in unit tests
3. **Use existing fixtures**: Check `conftest.py` and `fixtures/` first
4. **Name descriptively**: `test_<function>_<scenario>_<expected_result>`
5. **Follow Given/When/Then**: Structure tests clearly

## Key Fixtures Reference

| Fixture | Location | Use Case |
|---------|----------|----------|
| `mock_service_registry` | `conftest.py` | Mock all services |
| `sample_ticker_info` | `conftest.py` | Standard ticker data |
| `sample_news_items` | `conftest.py` | News article fixtures |
| `in_memory_db` | `db_fixtures.py` | Fresh DuckDB instance |
| `db_with_portfolio` | `db_fixtures.py` | DB with sample positions |
| `mock_gemini_rate_limit_error` | `api_fixtures.py` | Gemini 429 error |
| `mock_ollama_success_response` | `api_fixtures.py` | Ollama response |

## CI/CD Integration

Tests run automatically on:
- Push to `main` or `develop`
- Pull requests to `main`

The workflow:
1. Runs unit tests with coverage
2. Runs integration tests
3. Uploads coverage to Codecov

## Troubleshooting

### Import Errors
```bash
# Ensure project root is in path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Singleton Leakage
Reset singletons between tests:
```python
@pytest.fixture
def cache_service():
    from phinan.services.cache_service import CacheService
    CacheService._instance = None
    yield CacheService()
    CacheService._instance = None
```

### Async Test Timeout
```python
@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_slow_async_operation():
    ...
```
