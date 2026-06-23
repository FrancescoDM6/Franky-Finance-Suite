"""Tests for pure Research indexing and cache helpers."""

import pytest


@pytest.mark.integration
class TestLRUCache:
    def test_lru_cache_get_set(self):
        from phinan.modules.research.research_cache import LRUCache

        cache = LRUCache(max_size=3, ttl=300)

        cache.set("key1", {"data": "value1"})

        result = cache.get("key1")

        assert result == {"data": "value1"}

    def test_lru_cache_evicts_oldest(self):
        from phinan.modules.research.research_cache import LRUCache

        cache = LRUCache(max_size=2, ttl=300)

        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        cache.set("key3", {"data": "value3"})

        assert cache.get("key1") is None
        assert cache.get("key2") == {"data": "value2"}
        assert cache.get("key3") == {"data": "value3"}

    def test_lru_cache_access_moves_to_end(self):
        from phinan.modules.research.research_cache import LRUCache

        cache = LRUCache(max_size=2, ttl=300)

        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        cache.get("key1")

        cache.set("key3", {"data": "value3"})

        assert cache.get("key1") == {"data": "value1"}
        assert cache.get("key2") is None
        assert cache.get("key3") == {"data": "value3"}

    def test_lru_cache_clear(self):
        from phinan.modules.research.research_cache import LRUCache

        cache = LRUCache(max_size=3, ttl=300)
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        cache.clear()

        assert cache.size() == 0
        assert cache.get("key1") is None


@pytest.mark.integration
class TestTickerIndex:
    def test_ticker_index_exact_match(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()
        index.build(
            [
                {"symbol": "AAPL", "name": "Apple Inc."},
                {"symbol": "AMZN", "name": "Amazon.com Inc."},
                {"symbol": "GOOGL", "name": "Alphabet Inc."},
            ]
        )

        results = index.search("AAPL", limit=10)

        assert len(results) >= 1
        assert results[0] == "AAPL - Apple Inc."

    def test_ticker_index_prefix_match(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()
        index.build(
            [
                {"symbol": "AAPL", "name": "Apple Inc."},
                {"symbol": "AMZN", "name": "Amazon.com Inc."},
                {"symbol": "AMD", "name": "Advanced Micro Devices"},
            ]
        )

        results = index.search("A", limit=10)

        assert len(results) == 3
        symbols = [r.split(" - ")[0] for r in results]
        assert "AAPL" in symbols
        assert "AMZN" in symbols
        assert "AMD" in symbols

    def test_ticker_index_name_word_match(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()
        index.build(
            [
                {"symbol": "AAPL", "name": "Apple Inc."},
                {"symbol": "MSFT", "name": "Microsoft Corporation"},
            ]
        )

        results = index.search("MICRO", limit=10)

        assert len(results) >= 1
        assert any("MSFT" in r for r in results)

    def test_ticker_index_empty_query(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()
        index.build(
            [
                {"symbol": "AAPL", "name": "Apple Inc."},
            ]
        )

        results = index.search("", limit=10)

        assert results == []

    def test_ticker_index_not_initialized(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()

        results = index.search("AAPL", limit=10)

        assert results == []

    def test_ticker_index_respects_limit(self):
        from phinan.modules.research.ticker_index import TickerIndex

        index = TickerIndex()
        index.build([{"symbol": f"A{i}", "name": f"Company {i}"} for i in range(20)])

        results = index.search("A", limit=5)

        assert len(results) == 5


@pytest.mark.integration
class TestComputeQualityCheck:
    def test_clean_fundamentals_pass(self):
        from phinan.modules.research.research_logic import compute_quality_check

        result = compute_quality_check(
            {
                "industry": "Tech",
                "dividend_yield": 0.04,
                "profit_margin": 0.25,
                "debt_to_equity": 0.5,
                "pe_ratio": 20,
            }
        )

        assert result["overall"] == "Pass"
        assert result["flags"] == []
        assert result["industry"] == "Tech"

    def test_two_or_more_flags_review(self):
        from phinan.modules.research.research_logic import compute_quality_check

        result = compute_quality_check(
            {"dividend_yield": 0.0, "profit_margin": 0.0, "debt_to_equity": 3}
        )

        assert result["overall"] == "Review"
        assert len(result["flags"]) >= 2

    def test_negative_pe_flagged(self):
        from phinan.modules.research.research_logic import compute_quality_check

        result = compute_quality_check(
            {"dividend_yield": 0.04, "profit_margin": 0.25, "pe_ratio": -5}
        )

        assert any("Negative P/E" in f for f in result["flags"])

    def test_missing_fields_default_to_zero(self):
        from phinan.modules.research.research_logic import compute_quality_check

        result = compute_quality_check({})

        assert result["industry"] == "Unknown"
        assert result["pe_ratio"] is None


@pytest.mark.integration
class TestComputeAggregateSentiment:
    class _News:
        def __init__(self, label, score):
            self.sentiment_label = label
            self.sentiment_score = score

    def test_empty_returns_empty_dict(self):
        from phinan.modules.research.research_logic import compute_aggregate_sentiment

        assert compute_aggregate_sentiment([]) == {}

    def test_counts_and_dominant(self):
        from phinan.modules.research.research_logic import compute_aggregate_sentiment

        news = [
            self._News("positive", 0.9),
            self._News("positive", 0.7),
            self._News("negative", 0.4),
        ]

        result = compute_aggregate_sentiment(news)

        assert result["dominant"] == "positive"
        assert result["counts"] == {"positive": 2, "negative": 1, "neutral": 0}
        assert result["total"] == 3
        assert result["average_confidence"] == round((0.9 + 0.7 + 0.4) / 3, 2)


