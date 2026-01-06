"""OpenBB Integration Tests

Run with: python scripts/test_openbb.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path so phinan can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def log(msg: str):
    """Print with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def test_openbb_import():
    """Test that OpenBB can be imported."""
    log("Testing OpenBB import...")
    try:
        from openbb import obb
        log("  [PASS] OpenBB imported successfully")
        return True, obb
    except ImportError as e:
        log(f"  [FAIL] ImportError: {e}")
        return False, None
    except Exception as e:
        log(f"  [FAIL] Unexpected error: {e}")
        return False, None


def test_openbb_profile(obb, symbol="AAPL"):
    """Test equity profile endpoint."""
    log(f"Testing obb.equity.profile('{symbol}')...")
    try:
        result = obb.equity.profile(symbol, provider="yfinance")
        if hasattr(result, "results") and result.results:
            data = result.results[0]
            name = getattr(data, "name", None) or getattr(data, "legal_name", "N/A")
            log(f"  [PASS] Got profile: {name}")
            return True
        else:
            log("  [FAIL] No results returned")
            return False
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        return False


def test_openbb_quote(obb, symbol="AAPL"):
    """Test equity quote endpoint."""
    log(f"Testing obb.equity.price.quote('{symbol}')...")
    try:
        result = obb.equity.price.quote(symbol, provider="yfinance")
        if hasattr(result, "results") and result.results:
            price = getattr(result.results[0], "last_price", None)
            log(f"  [PASS] Got quote: {price}")
            return True
        else:
            log("  [FAIL] No results returned")
            return False
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        return False


def test_openbb_historical(obb, symbol="AAPL"):
    """Test price history endpoint."""
    log(f"Testing obb.equity.price.historical('{symbol}')...")
    try:
        result = obb.equity.price.historical(
            symbol, start_date="2024-01-01", provider="yfinance"
        )
        if hasattr(result, "results") and result.results:
            df = result.to_df()
            log(f"  [PASS] Got {len(df)} rows of price history")
            return True
        else:
            log("  [FAIL] No results returned")
            return False
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        return False


def test_openbb_news(obb, symbol="AAPL"):
    """Test news endpoint."""
    log(f"Testing obb.news.company('{symbol}')...")
    try:
        result = obb.news.company(symbol, limit=5, provider="yfinance")
        if hasattr(result, "results") and result.results:
            log(f"  [PASS] Got {len(result.results)} news articles")
            return True
        else:
            log("  [WARN] No news results (may be normal)")
            return True
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        return False


def test_market_data_service():
    """Test the MarketDataService with OpenBB provider."""
    log("Testing MarketDataService...")
    try:
        from phinan.services.market_data import MarketDataService

        svc = MarketDataService()
        log(f"  Provider: {svc._provider_name}")

        info = svc.get_ticker_info("MSFT")
        if info:
            log(f"  [PASS] get_ticker_info: {info.name}")
        else:
            log("  [FAIL] get_ticker_info returned None")
            return False

        history = svc.get_price_history("MSFT", period="1mo")
        if not history.empty:
            log(f"  [PASS] get_price_history: {len(history)} rows")
        else:
            log("  [FAIL] get_price_history returned empty DataFrame")
            return False

        news = svc.get_news("MSFT", max_items=3)
        log(f"  [PASS] get_news: {len(news)} articles")

        return True
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_circuit_breaker():
    """Test circuit breaker integration."""
    log("Testing CircuitBreaker...")
    try:
        from phinan.services.circuit_breaker import get_circuit_breaker

        breaker = get_circuit_breaker("openbb")
        state = breaker.get_state()
        log(f"  [PASS] Circuit state: {state['state']}, failures: {state['failure_count']}")
        return True
    except Exception as e:
        log(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all OpenBB tests."""
    print("")
    print("OpenBB Integration Test Suite")
    print("-" * 40)
    print("")

    results = {}

    success, obb = test_openbb_import()
    results["import"] = success

    if obb:
        results["profile"] = test_openbb_profile(obb)
        results["quote"] = test_openbb_quote(obb)
        results["historical"] = test_openbb_historical(obb)
        results["news"] = test_openbb_news(obb)

    results["service"] = test_market_data_service()
    results["circuit_breaker"] = test_circuit_breaker()

    print("")
    print("-" * 40)
    print("RESULTS SUMMARY")
    print("-" * 40)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {test}: [{status}]")

    print("")
    print(f"Total: {passed}/{total} tests passed")
    print("-" * 40)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
