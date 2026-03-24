# Embedding Generator for Memory System

from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator

from memory.models import EmbeddingModelConfig


class EmbeddingGenerator:
    """Generate text embeddings using sentence-transformers.

    This class provides an interface to generate embeddings for text content
    to enable semantic similarity search in the memory system.

    Supports:
    - Sentence-transformers models (default)
    - Local execution (no cloud dependencies)
    - Batch processing for efficiency
    - Normalized embeddings for cosine similarity
    """

    def __init__(self, config: EmbeddingModelConfig | None = None):
        """Initialize the embedding generator.

        Args:
            config: Configuration for embedding generation
        """
        self.config = config or EmbeddingModelConfig()
        self._model = None
        self._is_loaded = False

    def _load_model(self):
        """Load the embedding model lazily."""
        if self._is_loaded:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device,
            )
            self._is_loaded = True
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load embedding model: {e}")

    @property
    def embedding_dim(self) -> int:
        """Get the dimension of the embedding space."""
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    def encode(
        self,
        text: str,
        normalize: bool | None = None,
    ) -> list[float]:
        """Encode a single text string into an embedding vector.

        Args:
            text: Input text to encode
            normalize: Whether to normalize embeddings (defaults to config setting)

        Returns:
            Embedding vector as list of floats
        """
        self._load_model()

        if normalize is None:
            normalize = self.config.normalize_embeddings

        embedding = self._model.encode(
            text,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
        )

        return embedding.tolist()

    def encode_batch(
        self,
        texts: list[str],
        normalize: bool | None = None,
    ) -> list[list[float]]:
        """Encode multiple texts into embeddings.

        Args:
            texts: List of input texts
            normalize: Whether to normalize embeddings (defaults to config setting)

        Returns:
            List of embedding vectors
        """
        self._load_model()

        if normalize is None:
            normalize = self.config.normalize_embeddings

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            batch_size=self.config.batch_size,
        )

        if len(texts) == 1 and embeddings.ndim == 1:
            return [embeddings.tolist()]
        elif embeddings.ndim == 2:
            return embeddings.tolist()
        else:
            return [emb.tolist() for emb in embeddings]

    def encode_dict(
        self,
        data: dict[str, Any],
        fields_to_encode: list[str] | None = None,
        normalize: bool | None = None,
    ) -> dict[str, list[float]]:
        """Encode specific fields from a dictionary.

        Args:
            data: Input dictionary
            fields_to_encode: List of field names to encode (default: all string fields)
            normalize: Whether to normalize embeddings

        Returns:
            Dictionary of field_name -> embedding
        """
        if fields_to_encode is None:
            fields_to_encode = [
                k for k, v in data.items()
                if isinstance(v, str) and len(v.strip()) > 0
            ]

        embeddings = {}
        for field in fields_to_encode:
            text = str(data.get(field, ""))
            if len(text.strip()) > 0:
                embeddings[field] = self.encode(text, normalize=normalize)

        return embeddings

    def generate_search_embedding(
        self,
        query: str,
        normalize: bool | None = None,
    ) -> list[float]:
        """Generate embedding optimized for search queries.

        Args:
            query: Search query text
            normalize: Whether to normalize (default from config)

        Returns:
            Embedding vector
        """
        # For search queries, we might want to use a different encoding strategy
        # For now, use the same encoding
        return self.encode(query, normalize=normalize)

    def similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score [0, 1]
        """
        import numpy as np

        arr1 = np.array(embedding1, dtype=np.float32)
        arr2 = np.array(embedding2, dtype=np.float32)

        # Compute cosine similarity
        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def batch_similarity(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
    ) -> list[float]:
        """Calculate similarity between query and multiple candidates.

        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings

        Returns:
            List of similarity scores [0, 1]
        """
        import numpy as np

        query_arr = np.array(query_embedding, dtype=np.float32)
        candidates_arr = np.array(candidate_embeddings, dtype=np.float32)

        # Compute dot products in batch
        dot_products = np.dot(candidates_arr, query_arr)

        # Compute norms
        query_norm = np.linalg.norm(query_arr)
        candidate_norms = np.linalg.norm(candidates_arr, axis=1)

        # Avoid division by zero
        if query_norm == 0:
            return [0.0] * len(candidate_embeddings)

        valid_mask = candidate_norms > 0
        similarities = np.zeros(len(candidate_embeddings), dtype=np.float32)
        similarities[valid_mask] = dot_products[valid_mask] / (candidate_norms[valid_mask] * query_norm)

        return similarities.tolist()

    def is_available(self) -> bool:
        """Check if the embedding generator is ready."""
        try:
            self._load_model()
            return True
        except Exception:
            return False

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model.

        Returns:
            Dictionary with model information
        """
        self._load_model()

        return {
            "model_name": self.config.model_name,
            "device": self.config.device,
            "embedding_dim": self.embedding_dim,
            "normalize_embeddings": self.config.normalize_embeddings,
            "max_seq_length": getattr(self._model, "max_seq_length", None),
        }
