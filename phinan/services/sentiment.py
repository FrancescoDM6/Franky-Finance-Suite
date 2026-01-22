"""Sentiment analysis service with lightweight TF-IDF + LR model.

Uses a pre-trained TF-IDF + Logistic Regression model for fast, local 
sentiment scoring. Falls back to LLM for missing model or low confidence.
"""

from typing import Optional, TYPE_CHECKING
import json
import logging
from pathlib import Path

from ..config.settings import settings

if TYPE_CHECKING:
    from .llm import LLMService

logger = logging.getLogger(__name__)

# Confidence threshold - below this, we use LLM fallback
CONFIDENCE_THRESHOLD = 0.5

# Label mapping for the model  
LABEL_NAMES = ["negative", "neutral", "positive"]


# Global model cache to prevent reloading across service instantiations
_GLOBAL_MODEL = None
_GLOBAL_MODEL_LOADED = False


class SentimentService:
    """Lightweight sentiment analysis service.

    Uses TF-IDF + Logistic Regression trained on Financial PhraseBank.
    Falls back to LLM for low-confidence predictions.
    """

    def __init__(self, llm_service: Optional["LLMService"] = None):
        """Initialize sentiment service.
        
        Args:
            llm_service: Optional LLM service for fallback scoring.
        """
        # No local state for model anymore, usage global cache
        self._model_path = Path(__file__).parent.parent / "data" / "sentiment_model.joblib"
        self._enabled = settings.ai_services.enable_sentiment
        self._llm_service = llm_service
        self._llm_enabled = True

    def _load_model(self):
        """Lazy-load the TF-IDF model into global cache."""
        global _GLOBAL_MODEL, _GLOBAL_MODEL_LOADED
        
        if _GLOBAL_MODEL_LOADED:
            return
        
        _GLOBAL_MODEL_LOADED = True
        
        if not self._enabled:
            logger.info("Sentiment service disabled via settings")
            return
            
        if not self._model_path.exists():
            logger.warning(
                f"Sentiment model not found at {self._model_path}. "
                "Run 'python scripts/train_sentiment_model.py' to train it."
            )
            return
            
        try:
            import joblib
            _GLOBAL_MODEL = joblib.load(self._model_path)
            logger.info(f"Loaded sentiment model from {self._model_path}")
        except Exception as e:
            logger.error(f"Error loading sentiment model: {e}")
            _GLOBAL_MODEL = None

    def health_check(self) -> bool:
        """Check if sentiment service is available."""
        self._load_model()
        return _GLOBAL_MODEL is not None or self._llm_service is not None

    def score(self, text: str) -> dict:
        """Score sentiment of a single text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with "label", "score", and "source" keys
        """
        results = self.score_batch([text])
        return results[0] if results else {"label": "neutral", "score": 0.5}

    def score_batch(self, texts: list[str]) -> list[dict]:
        """Score sentiment of multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            List of sentiment dicts with label, score, source
        """
        if not texts:
            return []
            
        self._load_model()

        if _GLOBAL_MODEL is None:
            # No local model - try LLM fallback or return neutral
            if self._llm_service and self._llm_enabled:
                return [self._score_with_llm(t) for t in texts]
            return [{"label": "neutral", "score": 0.5, "error": "No model available"} for _ in texts]

        results = []
        for text in texts:
            result = self._score_local(text)
            
            # LLM fallback for low confidence
            if (
                result["score"] < CONFIDENCE_THRESHOLD 
                and self._llm_service 
                and self._llm_enabled
            ):
                llm_result = self._score_with_llm(text)
                llm_result["local_original"] = result
                results.append(llm_result)
            else:
                results.append(result)
                
        return results

    def _score_local(self, text: str) -> dict:
        """Score using the local TF-IDF model."""
        try:
            pred_idx = _GLOBAL_MODEL.predict([text])[0]
            proba = _GLOBAL_MODEL.predict_proba([text])[0]
            confidence = float(proba[pred_idx])
            
            return {
                "label": LABEL_NAMES[pred_idx],
                "score": confidence,
                "scores": {LABEL_NAMES[i]: float(proba[i]) for i in range(len(LABEL_NAMES))},
                "source": "local"
            }
        except Exception as e:
            logger.error(f"Local sentiment error: {e}")
            return {"label": "neutral", "score": 0.5, "error": str(e), "source": "local"}

    def _score_with_llm(self, text: str) -> dict:
        """Score using LLM fallback."""
        if not self._llm_service:
            return {"label": "neutral", "score": 0.5, "error": "No LLM service", "source": "llm"}
            
        prompt = f"""Analyze the sentiment of this financial news headline for its likely impact on stock price.

Headline: "{text}"

Respond with ONLY a JSON object (no markdown, no explanation):
{{"label": "positive" or "negative" or "neutral", "score": 0.0-1.0, "reasoning": "brief explanation"}}

Guidelines:
- "positive" = likely good for stock price
- "negative" = likely bad for stock price  
- "neutral" = factual/informational with no clear price impact
- Score should reflect confidence (1.0 = very confident)"""

        try:
            response = self._llm_service.complete(prompt)
            
            # Parse JSON response
            cleaned = response.strip()
            if cleaned.startswith("```"):
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
            logger.warning(f"LLM response not valid JSON: {response[:100] if response else 'empty'}")
            return {"label": "neutral", "score": 0.5, "error": "parse_error", "source": "llm"}
        except Exception as e:
            logger.error(f"LLM sentiment error: {e}")
            return {"label": "neutral", "score": 0.5, "error": str(e), "source": "llm"}

    def aggregate(self, texts: list[str]) -> dict:
        """Calculate aggregate sentiment from multiple texts.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            Dict with counts, average_score, dominant label, and total
        """
        if not texts:
            return {
                "counts": {"positive": 0, "negative": 0, "neutral": 0},
                "average_score": 0.5,
                "dominant": "neutral",
                "total": 0,
            }
            
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
