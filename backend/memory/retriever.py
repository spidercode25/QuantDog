# Memory Retriever with Multi-Dimensional Scoring

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

from memory.database import MemoryDatabase
from memory.embedding import EmbeddingGenerator
from memory.models import (
    Memory,
    MemoryQuery,
    MemoryRetrievalConfig,
)


class MemoryRetriever:
    """Memory retrieval engine with multi-dimensional scoring.

    Implements the memory recall scoring formula:
    score = w_sim × similarity + w_recency × recency + w_returns × returns_score

    Dimensions:
    1. Semantic similarity: Cosine similarity between query and memory embeddings
    2. Recency: Time decay score, higher for recent memories
    3. Historical returns: Past decision PnL performance

    All scores are normalized to [0, 1] and combined using configurable weights.
    """

    def __init__(
        self,
        database: MemoryDatabase,
        config: MemoryRetrievalConfig | None = None,
        embedder: EmbeddingGenerator | None = None,
    ):
        """Initialize the memory retriever.

        Args:
            database: MemoryDatabase instance
            config: Retrieval configuration
            embedder: EmbeddingGenerator instance (optional, will create if not provided)
        """
        self._db = database
        self._config = config or MemoryRetrievalConfig()
        self._embedder = embedder or EmbeddingGenerator()

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        """Retrieve memories matching the query using multi-dimensional scoring.

        Args:
            query: MemoryQuery object with search parameters

        Returns:
            List of Memory objects sorted by composite_score
        """
        # 1. Search for semantically similar memories
        memories = self._db.search_similar_memories(
            agent_name=query.agent_name,
            query_embedding=query.query_embedding,
            top_k=query.top_k * 2,  # Fetch more for filtering
            min_threshold=query.min_confidence,
        )

        if not memories:
            return []

        # 2. Calculate multi-dimensional scores for each memory
        scored_memories = []
        for memory in memories:
            scores = self._calculate_scores(memory, query)
            memory.similarity_score = scores["similarity"]
            memory.recency_score = scores["recency"]
            memory.returns_score = scores["returns"]
            memory.composite_score = scores["composite"]

            scored_memories.append(memory)

        # 3. Filter and update database scores
        for memory in scored_memories:
            self._db.update_memory(
                update=MemoryUpdate(
                    memory_id=memory.id,
                    similarity_score=memory.similarity_score,
                    recency_score=memory.recency_score,
                    returns_score=memory.returns_score,
                    composite_score=memory.composite_score,
                )
            )

        # 4. Sort by composite score and apply filters
        scored_memories.sort(key=lambda m: m.composite_score, reverse=True)

        # Filter by time horizon if specified
        if query.time_horizon:
            scored_memories = [
                m for m in scored_memories
                if m.created_at >= query.time_horizon
            ]

        # Filter by memory type if specified
        if query.memory_types:
            scored_memories = [
                m for m in scored_memories
                if m.memory_type in query.memory_types
            ]

        # Return top_k results
        return scored_memories[: query.top_k]

    def _calculate_scores(
        self,
        memory: Memory,
        query: MemoryQuery,
    ) -> dict[str, float]:
        """Calculate multi-dimensional scores for a memory.

        Args:
            memory: Memory object
            query: Query object

        Returns:
            Dictionary with similarity, recency, returns, and composite scores
        """
        # 1. Calculate similarity score (already computed during search)
        similarity = memory.similarity_score

        # 2. Calculate recency score using time decay
        recency = self._calculate_recency_score(memory.created_at)

        # 3. Calculate returns score from historical outcomes
        returns_score = self._calculate_returns_score(memory)

        # 4. Calculate composite score using weighted formula
        composite = (
            self._config.w_similarity * similarity +
            self._config.w_recency * recency +
            self._config.w_returns * returns_score
        )

        return {
            "similarity": similarity,
            "recency": recency,
            "returns": returns_score,
            "composite": composite,
        }

    def _calculate_recency_score(self, created_at: datetime) -> float:
        """Calculate recency score using exponential time decay.

        Formula: recency = exp(-Δt / half_life)

        Args:
            created_at: When the memory was created

        Returns:
            Recency score [0, 1]
        """
        now = datetime.utcnow()
        delta = (now - created_at).total_seconds()  # in seconds
        half_life_seconds = self._config.recency_half_life_days * 24 * 3600

        # Exponential decay
        recency = math.exp(-delta / half_life_seconds)

        return recency

    def _calculate_returns_score(self, memory: Memory) -> float:
        """Calculate returns score from historical decision outcomes.

        Strategy:
        - For past BUY decisions with positive PnL: score = normalized(PnL%)
        - For past BUY decisions with negative PnL: score = 0
        - For past SELL decisions with negative PnL: score = normalized(abs(PnL%))
        - For past SELL decisions with positive PnL: score = 0
        - For HOLD decisions: score based on correctness

        Args:
            memory: Memory object

        Returns:
            Returns score [0, 1]
        """
        # Check if memory already has a returns_score
        if memory.returns_score > 0:
            return memory.returns_score

        # Get outcomes for this memory if available
        decision_type = memory.metadata.get("decision", "").upper()

        # If no outcome data available, return neutral score
        if "pnl_percent" not in memory.metadata:
            return 0.5

        pnl_percent = memory.metadata["pnl_percent"]

        if decision_type == "BUY":
            # BUY: positive PnL is good
            if pnl_percent > 0:
                # Normalize positive returns (assuming 50% = perfect)
                return min(pnl_percent / 50.0, 1.0)
            else:
                return 0.0

        elif decision_type == "SELL":
            # SELL: negative PnL is good
            if pnl_percent < 0:
                # Normalize negative returns (assuming -50% = perfect)
                return min(abs(pnl_percent) / 50.0, 1.0)
            else:
                return 0.0

        elif decision_type == "HOLD":
            # HOLD: direction matters
            # If we held and market went against us, good HOLD decision
            # If we held and market moved our way, could have traded
            # Assume neutral for now
            return 0.5

        else:
            return 0.5

    def update_weights(
        self,
        w_similarity: float | None = None,
        w_recency: float | None = None,
        w_returns: float | None = None,
    ):
        """Update the scoring weights.

        Args:
            w_similarity: New similarity weight [0, 1]
            w_recency: New recency weight [0, 1]
            w_returns: New returns weight [0, 1]
        """
        if w_similarity is not None:
            self._config.w_similarity = w_similarity
        if w_recency is not None:
            self._config.w_recency = w_recency
        if w_returns is not None:
            self._config.w_returns = w_returns

        # Normalize weights if they don't sum to 1
        total = (
            self._config.w_similarity +
            self._config.w_recency +
            self._config.w_returns
        )
        if total > 0 and total != 1.0:
            self._config.w_similarity /= total
            self._config.w_recency /= total
            self._config.w_returns /= total

    def get_config(self) -> dict[str, Any]:
        """Get current retrieval configuration.

        Returns:
            Dictionary with configuration values
        """
        return {
            "weights": {
                "similarity": self._config.w_similarity,
                "recency": self._config.w_recency,
                "returns": self._config.w_returns,
            },
            "recency_half_life_days": self._config.recency_half_life_days,
            "similarity_threshold": self._config.similarity_threshold,
            "top_k": self._config.top_k,
        }

    def explain_scores(self, memory: Memory) -> dict[str, Any]:
        """Explain the scoring for a specific memory.

        Args:
            memory: Memory object

        Returns:
            Dictionary with score explanation
        """
        explanation = {
            "memory_id": memory.id,
            "memory_type": memory.memory_type,
            "embedding_model": memory.embedding_model,
            "scores": {
                "similarity": {
                    "value": memory.similarity_score,
                    "weight": self._config.w_similarity,
                    "contribution": memory.similarity_score * self._config.w_similarity,
                    "interpretation": self._interpret_similarity_score(memory.similarity_score),
                },
                "recency": {
                    "value": memory.recency_score,
                    "weight": self._config.w_recency,
                    "contribution": memory.recency_score * self._config.w_recency,
                    "interpretation": self._interpret_recency_score(memory.recency_score),
                },
                "returns": {
                    "value": memory.returns_score,
                    "weight": self._config.w_returns,
                    "contribution": memory.returns_score * self._config.w_returns,
                    "interpretation": self._interpret_returns_score(memory.returns_score),
                },
                "composite": {
                    "value": memory.composite_score,
                    "formula": f"{self._config.w_similarity}×{memory.similarity_score:.3f} + "
                              f"{self._config.w_recency}×{memory.recency_score:.3f} + "
                              f"{self._config.w_returns}×{memory.returns_score:.3f}]",
                },
            },
            "metadata": memory.metadata,
        }

        return explanation

    def _interpret_similarity_score(self, score: float) -> str:
        """Interpret a similarity score."""
        if score >= 0.9:
            return "Very similar - highly relevant context"
        elif score >= 0.75:
            return "Similar - relevant context"
        elif score >= 0.6:
            return "Moderately similar - somewhat relevant"
        elif score >= 0.4:
            return "Low similarity - limited relevance"
        else:
            return "Not very similar - low relevance"

    def _interpret_recency_score(self, score: float) -> str:
        """Interpret a recency score."""
        if score >= 0.8:
            return "Very recent (last ~5 days)"
        elif score >= 0.5:
            return "Recent (last ~30 days)"
        elif score >= 0.3:
            return "Moderately recent (last ~60 days)"
        elif score >= 0.1:
            return "Older (last ~90 days)"
        else:
            return "Very old (90+ days)"

    def _interpret_returns_score(self, score: float) -> str:
        """Interpret a returns score."""
        if score >= 0.8:
            return "Excellent historical performance"
        elif score >= 0.6:
            return "Good historical performance"
        elif score >= 0.4:
            return "Moderate historical performance"
        elif score >= 0.2:
            return "Inconsistent performance"
        else:
            return "Poor or no historical data"
