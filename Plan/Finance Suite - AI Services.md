---
aliases:
  - ai services
  - ml services
  - finance ai
status: In progress
ai_summary: "AI services layer for Finance Suite. Includes LLM service (Ollama) for synthesis/explanation, FinBERT for sentiment analysis, GARCH for volatility forecasting, sentence-transformers for embeddings/similarity, and statistical anomaly detection. Clear separation between LLM tasks and specialized model tasks."
priority: Medium
start_date: 2024-12-28
end_date:
progress: 0
energy: Medium
domain:
  - AI
  - Finance
stage: Design
iec_score: 7.33
iec_impact: 8
iec_ease: 6
iec_confidence: 8
blocked: false
blocker:
files:
links:
integration_notes: "Lives in services/. Used by all modules and the assistant. Each service is independent and can be used standalone. LLM service is the most critical; others add value but aren't blockers."
integration_status: Planned
parent_project: "[[Finance Suite]]"
project_scope: Feature
tool_stack:
  - Python
  - Ollama
  - transformers
  - sentence-transformers
  - arch (GARCH)
categories:
  - "[[Projects]]"
  - "[[AI]]"
  - "[[Finance]]"
tags:
  - project
  - ai
  - llm
  - ml
  - finance
DateCreated: Monday, December 30th 2024
DateLastModified: Monday, December 30th 2024
---

## Overview

The AI services layer provides intelligence capabilities to all modules and the assistant. Key principle: **use the right tool for the job**.

| Task Type | Right Tool | Wrong Tool |
|-----------|------------|------------|
| Synthesis, explanation | LLM | - |
| Sentiment classification | FinBERT | LLM (slower, inconsistent) |
| Number extraction | OCR + regex | LLM (hallucinates) |
| Calculations | Python | LLM (bad at math) |
| Similarity search | Embeddings | LLM (can't batch) |
| Volatility forecast | GARCH | LLM (not trained for this) |
| Anomaly detection | Statistics | LLM (overkill) |

## Services

### 1. LLM Service (Ollama)

**When to use:** Synthesis, explanation, exploration, reflection, multi-turn conversations

**When NOT to use:** Extracting specific numbers, calculations, classification with clear categories

```python
class LLMService:
    def __init__(self, model: str = "llama3.1"):
        self.client = ollama.Client()
        self.model = model
    
    def chat(self, messages, system=None, tools=None): ...
    def complete(self, prompt, system=None): ...
    def structured_output(self, prompt, schema): ...
```

### 2. Sentiment Service (FinBERT)

**When to use:** Scoring news headlines, analyzing earnings calls, batch processing text

**Advantages over LLM:** 10-100x faster, consistent scores, batchable, trained on financial language

```python
class SentimentService:
    def score(self, text: str) -> dict:
        # Returns {"label": "positive"|"negative"|"neutral", "score": 0.0-1.0}
    
    def score_batch(self, texts: list[str]) -> list[dict]: ...
    
    def aggregate(self, texts: list[str]) -> dict:
        # Returns overall sentiment from multiple texts
```

### 3. Volatility Service (GARCH)

**When to use:** Forecasting future volatility, improving range estimates, assessing if options are cheap/expensive

```python
class VolatilityService:
    def forecast(self, returns: pd.Series, horizon: int = 5) -> dict:
        # Returns forecast and current vol estimates
    
    def expected_range(self, current_price, returns, days=5, confidence=0.68) -> dict:
        # Returns expected price range using GARCH forecast
```

### 4. Embedding Service (Similarity Search)

**When to use:** "Find stocks similar to X", clustering news articles, deduplicating news

```python
class EmbeddingService:
    def __init__(self, model="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model)
    
    def find_similar(self, query: str, candidates: list[str], top_k=5): ...
    def cluster_texts(self, texts: list[str], n_clusters=5): ...
```

### 5. Anomaly Detection (Statistical)

**When to use:** Unusual options volume, abnormal price movements, spotting potential news before public

```python
class AnomalyService:
    def detect_volume_anomaly(self, current, historical) -> Optional[Anomaly]: ...
    def detect_options_anomalies(self, chain, historical_chain) -> list[Anomaly]: ...
```

### 6. PDF Extraction (OCR)

**When to use:** Parsing structured note term sheets, extracting data from financial reports

**Why OCR over LLM:** Deterministic, faster, doesn't hallucinate numbers, handles complex layouts

```python
class PDFService:
    def extract_text(self, pdf_path: str) -> str: ...
    def extract_structured_note_terms(self, pdf_path: str) -> dict: ...
```

## Service Registry

```python
# services/__init__.py
class Services:
    """Lazy-loaded service registry."""
    
    @property
    def llm(self) -> LLMService: ...
    
    @property
    def sentiment(self) -> SentimentService: ...
    
    # etc.

services = Services()

# Usage:
# from services import services
# services.llm.complete("...")
# services.sentiment.score("...")
```

## Priority & Build Order

1. **LLM Service** - Required for assistant, blocks nothing else
2. **Market Data Service** - Required for research module
3. **Sentiment Service** - Enhances research, can add later
4. **Volatility Service** - Enhances range estimates, can add later
5. **PDF Service** - Required for Notes module PDF parsing
6. **Embeddings Service** - Nice to have for similarity features
7. **Anomaly Service** - Nice to have for options module

## Related

- [[Finance Suite]] (parent)
- [[Finance Suite - Assistant]] (primary consumer of LLM service)
- [[Finance Suite - Research Module]] (uses sentiment, volatility)
- [[Finance Suite - Notes Module]] (uses PDF extraction)

---
Created: 2024-12-30
