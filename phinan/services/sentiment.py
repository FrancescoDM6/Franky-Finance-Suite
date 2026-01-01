"""Sentiment analysis service using FinBERT.

FinBERT is 10-100x faster than LLM for sentiment classification
and trained specifically on financial language.

Use for: scoring news headlines, analyzing earnings calls, batch processing text
"""

from typing import Optional

from ..config.settings import settings


class SentimentService:
    """FinBERT-based sentiment analysis service.

    Lazy-loads the model on first use to avoid startup delay.
    """

    def __init__(self):
        """Initialize sentiment service."""
        self._model = None
        self._tokenizer = None
        self._model_name = settings.ai_services.sentiment_model
        self._enabled = settings.ai_services.enable_sentiment

    def _load_model(self):
        """Lazy-load FinBERT model."""
        if not self._enabled:
            return

        if self._model is None:
            try:
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                print(f"Loading sentiment model: {self._model_name}...")
                self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)
                print("Sentiment model loaded successfully")
            except Exception as e:
                print(f"Error loading sentiment model: {e}")
                self._enabled = False  # Disable if failed to load


    def health_check(self) -> bool:
        """Check if sentiment service is available (without loading model)."""
        # Don't trigger model load here - just check if enabled
        return self._enabled

    def score(self, text: str) -> dict:
        """Score sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Dict with "label" (positive/negative/neutral) and "score" (0-1)
        """
        if not self._enabled:
            return {"label": "neutral", "score": 0.5, "enabled": False}

        self._load_model()

        if self._model is None:
            return {"label": "neutral", "score": 0.5, "error": "Model not loaded"}

        try:
            import torch

            inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

            with torch.no_grad():
                outputs = self._model(**inputs)
                scores = torch.softmax(outputs.logits, dim=1)

            # FinBERT labels: positive, negative, neutral
            labels = ["positive", "negative", "neutral"]
            max_idx = scores.argmax().item()

            return {
                "label": labels[max_idx],
                "score": float(scores[0][max_idx]),
                "scores": {label: float(scores[0][i]) for i, label in enumerate(labels)},
            }
        except Exception as e:
            return {"label": "neutral", "score": 0.5, "error": str(e)}

    def score_batch(self, texts: list[str]) -> list[dict]:
        """Score sentiment of multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of sentiment dicts
        """
        return [self.score(text) for text in texts]

    def aggregate(self, texts: list[str]) -> dict:
        """Calculate aggregate sentiment from multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            Aggregate sentiment dict with counts and average
        """
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
