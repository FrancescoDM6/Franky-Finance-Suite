#!/usr/bin/env python3
"""Test script to analyze portfolio database query performance.

This script:
1. Runs EXPLAIN ANALYZE on all portfolio queries
2. Generates sample data for load testing
3. Compares performance before/after index creation
4. Outputs detailed performance reports

Usage:
    python migrations/test_query_performance.py
    python migrations/test_query_performance.py --generate-test-data
    python migrations/test_query_performance.py --compare-indexes
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phinan.core.database import get_database_manager


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def explain_query(db, query: str, params: tuple = (), label: str = "") -> dict[str, Any]:
    """Run EXPLAIN ANALYZE on a query and return results."""
    print(f"\n--- {label} ---")
    print(f"Query:\n{query}\n")

    # Add EXPLAIN ANALYZE prefix
    explain_query = f"EXPLAIN ANALYZE {query}"

    start = time.perf_counter()
    try:
        result = db.query(explain_query, params)
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        print("Execution Plan:")
        for row in result:
            print(row.get("explain_value", row))

        print(f"\nElapsed Time: {elapsed:.2f} ms")

        return {
            "label": label,
            "elapsed_ms": elapsed,
            "success": True,
            "plan": result,
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"ERROR: {e}")
        print(f"Elapsed Time: {elapsed:.2f} ms")

        return {
            "label": label,
            "elapsed_ms": elapsed,
            "success": False,
            "error": str(e),
        }


def test_portfolio_queries(db):
    """Test all portfolio-related queries."""
    print_section("Portfolio Query Performance Analysis")

    results = []

    # Query 1: Load all positions
    results.append(explain_query(
        db,
        """
        SELECT id, ticker_symbol, quantity, cost_basis, purchase_date, notes
        FROM portfolio
        ORDER BY ticker_symbol
        """,
        label="Load All Positions (Most Frequent)"
    ))

    # Query 2: Get position by ticker
    results.append(explain_query(
        db,
        """
        SELECT id, ticker_symbol, quantity, cost_basis, purchase_date, notes
        FROM portfolio
        WHERE ticker_symbol = ?
        LIMIT 1
        """,
        params=("AAPL",),
        label="Get Position by Ticker (Research Integration)"
    ))

    # Query 3: Delete position
    # Don't actually run DELETE in EXPLAIN mode, just show the plan
    print("\n--- Delete Position by ID ---")
    print("Query: DELETE FROM portfolio WHERE id = ?")
    print("Note: Uses PRIMARY KEY - optimal O(log n) performance")
    print("Not running EXPLAIN ANALYZE (would require write lock)")

    return results


def test_market_cache_queries(db):
    """Test market data cache queries."""
    print_section("Market Data Cache Query Performance")

    results = []

    # Query 1: Cache lookup (current implementation)
    results.append(explain_query(
        db,
        """
        SELECT data, cached_at, expires_at
        FROM market_data_cache
        WHERE ticker_symbol = ?
          AND data_type = ?
          AND expires_at > CURRENT_TIMESTAMP
        ORDER BY cached_at DESC
        LIMIT 1
        """,
        params=("AAPL", "ticker_info"),
        label="Market Cache Lookup (Pre-Optimization)"
    ))

    return results


def test_user_context_queries(db):
    """Test user context queries."""
    print_section("User Context Query Performance")

    results = []

    # Query 1: Batch key lookup
    results.append(explain_query(
        db,
        """
        SELECT key, value
        FROM user_context
        WHERE key IN (?, ?, ?, ?, ?, ?)
        """,
        params=(
            "active_profile",
            "watchlist",
            "default_range_period",
            "theme",
            "show_news",
            "show_analyst_details",
        ),
        label="Batch User Context Lookup"
    ))

    return results


def test_research_queries(db):
    """Test research table queries."""
    print_section("Research Table Query Performance")

    results = []

    # Query 1: Get research by ticker and type
    results.append(explain_query(
        db,
        """
        SELECT *
        FROM research
        WHERE ticker_symbol = ?
          AND research_type = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        params=("AAPL", "sentiment"),
        label="Get Research by Ticker and Type"
    ))

    return results


def generate_test_data(db, num_positions: int = 1000):
    """Generate test data for performance testing."""
    print_section(f"Generating {num_positions} Test Portfolio Positions")

    print("WARNING: This will insert test data into the database.")
    print("Make sure you're using a test database, not production!")
    response = input("Continue? (yes/no): ")

    if response.lower() != "yes":
        print("Aborted.")
        return

    print("\nGenerating test data...")
    start = time.perf_counter()

    try:
        db.execute(f"""
            INSERT INTO portfolio (ticker_symbol, quantity, cost_basis, purchase_date, notes)
            SELECT
                'TEST' || CAST(i AS VARCHAR) as ticker_symbol,
                RANDOM() * 100 as quantity,
                RANDOM() * 500 as cost_basis,
                DATE '2020-01-01' + INTERVAL (CAST(RANDOM() * 1000 AS INTEGER)) DAY as purchase_date,
                'Test position ' || CAST(i AS VARCHAR) as notes
            FROM generate_series(1, {num_positions}) AS t(i)
        """)

        elapsed = time.perf_counter() - start
        print(f"Generated {num_positions} positions in {elapsed:.2f} seconds")

        # Verify count
        result = db.query("SELECT COUNT(*) as count FROM portfolio")
        total_count = result[0]["count"] if result else 0
        print(f"Total positions in database: {total_count}")

    except Exception as e:
        print(f"ERROR: {e}")


def cleanup_test_data(db):
    """Remove test data from database."""
    print_section("Cleaning Up Test Data")

    print("Removing all positions with ticker_symbol starting with 'TEST'...")

    try:
        result = db.execute(
            "DELETE FROM portfolio WHERE ticker_symbol LIKE 'TEST%'"
        )
        print(f"Deleted test positions")

        # Verify
        result = db.query("SELECT COUNT(*) as count FROM portfolio")
        remaining = result[0]["count"] if result else 0
        print(f"Remaining positions: {remaining}")

    except Exception as e:
        print(f"ERROR: {e}")


def compare_index_performance(db):
    """Compare query performance before and after index creation."""
    print_section("Index Comparison Test")

    print("This test will:")
    print("1. Run market cache query with current indexes")
    print("2. Create optimized composite index")
    print("3. Run the same query again")
    print("4. Show performance difference")

    response = input("\nContinue? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return

    # Query to test
    test_query = """
        SELECT data, cached_at, expires_at
        FROM market_data_cache
        WHERE ticker_symbol = ?
          AND data_type = ?
          AND expires_at > CURRENT_TIMESTAMP
        ORDER BY cached_at DESC
        LIMIT 1
    """
    params = ("AAPL", "ticker_info")

    # Before optimization
    print("\n--- BEFORE: Current Index Strategy ---")
    before = explain_query(db, test_query, params, "Market Cache Lookup (Before)")

    # Create optimized index
    print("\n--- Creating Optimized Composite Index ---")
    try:
        db.execute("DROP INDEX IF EXISTS idx_market_cache_ticker")
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_cache_lookup
            ON market_data_cache(ticker_symbol, data_type, expires_at DESC)
        """)
        print("Index created: idx_market_cache_lookup")
    except Exception as e:
        print(f"ERROR creating index: {e}")
        return

    # After optimization
    print("\n--- AFTER: Optimized Composite Index ---")
    after = explain_query(db, test_query, params, "Market Cache Lookup (After)")

    # Compare
    print("\n" + "=" * 80)
    print("  Performance Comparison")
    print("=" * 80)
    print(f"\nBefore: {before['elapsed_ms']:.2f} ms")
    print(f"After:  {after['elapsed_ms']:.2f} ms")

    if before['elapsed_ms'] > 0:
        improvement = ((before['elapsed_ms'] - after['elapsed_ms']) / before['elapsed_ms']) * 100
        speedup = before['elapsed_ms'] / after['elapsed_ms']
        print(f"\nImprovement: {improvement:.1f}%")
        print(f"Speedup: {speedup:.2f}x faster")

    print("\nNote: Performance difference may be small for empty/small tables.")
    print("Try running with --generate-test-data for more realistic results.")


def show_database_stats(db):
    """Show database statistics."""
    print_section("Database Statistics")

    tables = ["portfolio", "market_data_cache", "user_context", "research",
              "options_positions", "chat_history"]

    for table in tables:
        try:
            result = db.query(f"SELECT COUNT(*) as count FROM {table}")
            count = result[0]["count"] if result else 0
            print(f"{table:25} {count:>10,} rows")
        except Exception as e:
            print(f"{table:25} ERROR: {e}")

    print("\n--- Indexes ---")
    try:
        indexes = db.query("SELECT * FROM duckdb_indexes()")
        for idx in indexes:
            print(f"{idx.get('index_name', 'N/A'):40} on {idx.get('table_name', 'N/A')}")
    except Exception as e:
        print(f"ERROR: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze portfolio database query performance"
    )
    parser.add_argument(
        "--generate-test-data",
        action="store_true",
        help="Generate 1000 test portfolio positions"
    )
    parser.add_argument(
        "--cleanup-test-data",
        action="store_true",
        help="Remove all test positions"
    )
    parser.add_argument(
        "--compare-indexes",
        action="store_true",
        help="Compare performance before/after index optimization"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics"
    )

    args = parser.parse_args()

    # Get database manager
    db = get_database_manager()

    # Show stats if requested or by default
    if args.stats or not any([args.generate_test_data, args.cleanup_test_data, args.compare_indexes]):
        show_database_stats(db)

    # Generate test data
    if args.generate_test_data:
        generate_test_data(db)

    # Cleanup test data
    if args.cleanup_test_data:
        cleanup_test_data(db)

    # Compare indexes
    if args.compare_indexes:
        compare_index_performance(db)

    # Run standard tests if no special flags
    if not any([args.generate_test_data, args.cleanup_test_data, args.compare_indexes]):
        test_portfolio_queries(db)
        test_market_cache_queries(db)
        test_user_context_queries(db)
        test_research_queries(db)

    print("\n" + "=" * 80)
    print("  Analysis Complete")
    print("=" * 80)
    print("\nFor detailed recommendations, see:")
    print("  docs/database-analysis.md")


if __name__ == "__main__":
    main()
