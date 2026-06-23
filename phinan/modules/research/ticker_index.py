"""Pre-built ticker index for fast Research autocomplete."""

class TickerIndex:
    """Pre-built index for fast ticker search.

    Instead of O(n) linear search on every keystroke,
    uses a symbol prefix index for O(1) average lookup.
    """

    def __init__(self):
        self._tickers: list[dict] = []
        self._symbol_to_ticker: dict[str, dict] = {}
        self._symbols_sorted: list[str] = []
        self._name_words: dict[str, list[dict]] = {}  # word -> list of tickers
        self._initialized = False

    def build(self, tickers: list[dict]) -> None:
        """Build search indices from ticker list."""
        self._tickers = tickers
        self._symbol_to_ticker = {t["symbol"]: t for t in tickers}
        self._symbols_sorted = sorted(self._symbol_to_ticker.keys())

        # Build name word index for partial name search
        self._name_words.clear()
        for t in tickers:
            name_upper = t.get("name", "").upper()
            # Index each word in the name
            for word in name_upper.split():
                if len(word) >= 2:  # Only index words with 2+ chars
                    if word not in self._name_words:
                        self._name_words[word] = []
                    self._name_words[word].append(t)

        self._initialized = True

    def search(self, query: str, limit: int = 10) -> list[str]:
        """Fast search for tickers matching query.

        Returns list of "SYMBOL - Name" strings.
        """
        if not self._initialized or not query:
            return []

        query_upper = query.upper()
        results = []
        seen = set()

        # 1. Exact symbol match (highest priority)
        if query_upper in self._symbol_to_ticker:
            t = self._symbol_to_ticker[query_upper]
            results.append(f"{t['symbol']} - {t['name']}")
            seen.add(t["symbol"])

        # 2. Symbol prefix matches
        for symbol in self._symbols_sorted:
            if len(results) >= limit:
                break
            if symbol.startswith(query_upper) and symbol not in seen:
                t = self._symbol_to_ticker[symbol]
                results.append(f"{t['symbol']} - {t['name']}")
                seen.add(symbol)

        # 3. Symbol contains query (if still need more)
        if len(results) < limit:
            for symbol in self._symbols_sorted:
                if len(results) >= limit:
                    break
                if query_upper in symbol and symbol not in seen:
                    t = self._symbol_to_ticker[symbol]
                    results.append(f"{t['symbol']} - {t['name']}")
                    seen.add(symbol)

        # 4. Name word matches (if still need more)
        if len(results) < limit:
            # Find tickers where any word in name starts with query
            for word, tickers in self._name_words.items():
                if len(results) >= limit:
                    break
                if word.startswith(query_upper):
                    for t in tickers:
                        if len(results) >= limit:
                            break
                        if t["symbol"] not in seen:
                            results.append(f"{t['symbol']} - {t['name']}")
                            seen.add(t["symbol"])

        return results[:limit]

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Built once and shared across Research state instances.
ticker_index = TickerIndex()

