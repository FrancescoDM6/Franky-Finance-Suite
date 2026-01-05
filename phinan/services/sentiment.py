"""Sentiment analysis service with hybrid FinBERT + LLM approach.

Uses FinBERT for fast batch processing, with LLM fallback for
low-confidence results to improve accuracy on ambiguous headlines.
"""

from typing import Optional, Protocol
import json

from ..config.settings import settings
from .resource_monitor import get_resource_monitor

import logging


# Confidence threshold - below this, we use LLM fallback
CONFIDENCE_THRESHOLD = 0.8


class LLMSentimentProvider(Protocol):
    """Protocol for LLM-based sentiment scoring (Ollama, Gemini, etc.)."""
    
    def score_sentiment(self, text: str) -> dict:
        """Score sentiment using LLM.
        
        Returns:
            Dict with "label" and "score" keys
        """
        ...


class OllamaSentimentProvider:
    """Ollama-based sentiment scoring for fallback."""
    
    SENTIMENT_PROMPT = """Analyze the sentiment of this financial news headline for its likely impact on stock price.

Headline: "{text}"

Respond with ONLY a JSON object (no markdown, no explanation):
{{"label": "positive" or "negative" or "neutral", "score": 0.0-1.0, "reasoning": "brief explanation"}}

Guidelines:
- "positive" = likely good for stock price (strong earnings, growth, partnerships, upgrades)
- "negative" = likely bad for stock price (losses, lawsuits, downgrades, regulatory issues)  
- "neutral" = factual/informational with no clear price impact
- Score should reflect confidence (1.0 = very confident, 0.5 = uncertain)"""

    def __init__(self):
        self._base_url = settings.ollama.base_url
        self._model = settings.ollama.model
        self._timeout = settings.ollama.timeout
    
    def score_sentiment(self, text: str) -> dict:
        """Score sentiment using Ollama LLM."""
        try:
            import httpx
            
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": self.SENTIMENT_PROMPT.format(text=text),
                    "stream": False,
                    "options": {"temperature": 0.1}  # Low temp for consistency
                },
                timeout=self._timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_response = result.get("response", "")
                
                # Parse JSON from response
                try:
                    # Clean up response if needed
                    cleaned = raw_response.strip()
                    if cleaned.startswith("```"):
                        # Remove markdown code blocks
                        cleaned = cleaned.split("```")[1]
                        if cleaned.startswith("json"):
                            cleaned = cleaned[4:]
                    
                    sentiment = json.loads(cleaned)
                    return {
                        "label": sentiment.get("label", "neutral").lower(),
                        "score": float(sentiment.get("score", 0.5)),
                        "reasoning": sentiment.get("reasoning", ""),
                        "source": "llm"
                    }
                except json.JSONDecodeError:
                    print(f"LLM response not valid JSON: {raw_response[:100]}")
                    return {"label": "neutral", "score": 0.5, "error": "parse_error", "source": "llm"}
            else:
                return {"label": "neutral", "score": 0.5, "error": f"http_{response.status_code}", "source": "llm"}
                
        except Exception as e:
            print(f"Ollama sentiment error: {e}")
            return {"label": "neutral", "score": 0.5, "error": str(e), "source": "llm"}


class SentimentService:
    """Hybrid sentiment analysis service.

    Uses FinBERT for fast batch processing, with LLM fallback
    for low-confidence results (<75%).
    """

    def __init__(self):
        """Initialize sentiment service."""
        self._model = None
        self._tokenizer = None
        self._device = None
        self._model_name = settings.ai_services.sentiment_model
        self._enabled = settings.ai_services.enable_sentiment
        self._llm_provider: Optional[LLMSentimentProvider] = None
        self._llm_enabled = True  # Can be toggled
        self._resource_monitor = get_resource_monitor()

    def _load_model(self):
        """Lazy-load FinBERT model with GPU support."""
        if not self._enabled:
            return
        
        # Check resource availability before loading heavy model
        if not self._resource_monitor.is_safe_to_run("local_sentiment"):
            logging.warning("⚠️ Insufficient resources for local sentiment, using LLM-only mode")
            self._enabled = False
            return

        if self._model is None:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                
                # Device selection: CUDA > MPS (Mac) > CPU
                if torch.cuda.is_available():
                    self._device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self._device = "mps"
                else:
                    self._device = "cpu"
                
                print(f"Loading sentiment model: {self._model_name} on {self._device}...")
                self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)
                self._model = self._model.to(self._device)
                self._model.eval()
                print("Sentiment model loaded successfully")
            except Exception as e:
                print(f"Error loading sentiment model: {e}")
                self._enabled = False

    def _get_llm_provider(self) -> LLMSentimentProvider:
        """Get or create LLM provider (lazy initialization)."""
        if self._llm_provider is None:
            # Currently uses Ollama - can swap to Gemini later
            self._llm_provider = OllamaSentimentProvider()
        return self._llm_provider

    def health_check(self) -> bool:
        """Check if sentiment service is available."""
        return self._enabled

    def score(self, text: str) -> dict:
        """Score sentiment of text with LLM fallback."""
        results = self.score_batch([text])
        return results[0] if results else {"label": "neutral", "score": 0.5}

    def score_batch(self, texts: list[str]) -> list[dict]:
        """Score sentiment of multiple texts with LLM fallback for low confidence.

        Args:
            texts: List of texts to analyze

        Returns:
            List of sentiment dicts
        """
        if not texts:
            return []
            
        if not self._enabled:
            return [{"label": "neutral", "score": 0.5, "enabled": False} for _ in texts]

        self._load_model()

        if self._model is None:
            return [{"label": "neutral", "score": 0.5, "error": "Model not loaded"} for _ in texts]

        # First pass: FinBERT batch scoring
        finbert_results = self._score_finbert_batch(texts)
        
        # Second pass: LLM fallback for low-confidence results
        if self._llm_enabled:
            final_results = []
            for i, result in enumerate(finbert_results):
                if result.get("score", 0) < CONFIDENCE_THRESHOLD:
                    # Low confidence - use LLM
                    llm_result = self._get_llm_provider().score_sentiment(texts[i])
                    llm_result["finbert_original"] = result  # Keep original for debugging
                    final_results.append(llm_result)
                else:
                    result["source"] = "finbert"
                    final_results.append(result)
            return final_results
        else:
            for result in finbert_results:
                result["source"] = "finbert"
            return finbert_results

    def _score_finbert_batch(self, texts: list[str]) -> list[dict]:
        """Score using FinBERT only (no fallback)."""
        try:
            import torch

            inputs = self._tokenizer(
                texts, 
                return_tensors="pt", 
                truncation=True, 
                max_length=512,
                padding=True
            )
            
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model(**inputs)
                batch_scores = torch.softmax(outputs.logits, dim=1)

            # Get labels from model config
            if hasattr(self._model.config, 'id2label'):
                id2label = self._model.config.id2label
                labels = [id2label[i].lower() for i in range(len(id2label))]
            else:
                labels = ["positive", "negative", "neutral"]
            
            results = []
            for i in range(len(texts)):
                scores = batch_scores[i]
                max_idx = scores.argmax().item()
                results.append({
                    "label": labels[max_idx],
                    "score": float(scores[max_idx]),
                    "scores": {labels[j]: float(scores[j]) for j in range(len(labels))},
                })
            
            return results
        except Exception as e:
            return [{"label": "neutral", "score": 0.5, "error": str(e)} for _ in texts]

    def aggregate(self, texts: list[str]) -> dict:
        """Calculate aggregate sentiment from multiple texts."""
        scores = self.score_batch(texts)

        counts = {"positive": 0, "negative": 0, "neutral": 0}
        total_score = 0

        for s in scores:
            label = s.get("label", "neutral")
            counts[label] = counts.get(label, 0) + 1
            total_score += s.get("score", 0.5)

        return {
            "counts": counts,
            "average_score": total_score / len(scores) if scores else 0.5,
            "dominant": max(counts, key=counts.get),
            "total": len(texts),
        }

