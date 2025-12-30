"""Embedding service for semantic similarity and search.

Use for: "find stocks similar to X", clustering news articles,
deduplicating news, semantic search in notes.
"""

from typing import Optional

from ..config.settings import settings


class EmbeddingService:
    """Sentence-transformers based embedding service."""

    def __init__(self):
        """Initialize embedding service."""
        self._model = None
        self._model_name = settings.ai_services.embedding_model
        self._enabled = settings.ai_services.enable_embeddings

    def _load_model(self):
        """Lazy-load embedding model."""
        if not self._enabled:
            return

        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                )

    def health_check(self) -> bool:
        """Check if embedding service is available."""
        if not self._enabled:
            return False
        try:
            self._load_model()
            return self._model is not None
        except Exception:
            return False

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        if not self._enabled:
            return []

        self._load_model()

        if self._model is None:
            return []

        try:
            embedding = self._model.encode(text)
            return embedding.tolist()
        except Exception:
            return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not self._enabled or not texts:
            return []

        self._load_model()

        if self._model is None:
            return []

        try:
            embeddings = self._model.encode(texts)
            return [e.tolist() for e in embeddings]
        except Exception:
            return []

    def find_similar(
        self,
        query: str,
        candidates: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float, str]]:
        """Find most similar texts to query.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score, text) tuples
        """
        if not self._enabled or not candidates:
            return []

        try:
            from sentence_transformers import util

            self._load_model()

            if self._model is None:
                return []

            query_embedding = self._model.encode(query)
            candidate_embeddings = self._model.encode(candidates)

            # Calculate cosine similarities
            similarities = util.cos_sim(query_embedding, candidate_embeddings)[0]

            # Get top-k indices
            top_indices = similarities.argsort(descending=True)[:top_k]

            results = []
            for idx in top_indices:
                results.append((int(idx), float(similarities[idx]), candidates[idx]))

            return results
        except Exception:
            return []
