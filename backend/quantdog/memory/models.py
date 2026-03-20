# Memory Layer Models

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str):
    """Types of memories stored by agents."""
    DECISION = "decision"
    OBSERVATION = "observation"
    REFLECTION = "reflection"


class Memory(BaseModel):
    """A stored memory from an agent's experience."""

    model_config = {"extra": "forbid"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = Field(description="Name of the agent who created this memory")
    memory_type: str = Field(description="Type of memory (decision, observation, reflection)")

    # Vector embedding
    embedding: list[float] = Field(description="Vector embedding of the memory content")
    embedding_model: str = Field(description="Model used to generate the embedding")

    # Content
    context: str = Field(description="Original context (JSON string)")
    content: str = Field(description="Stored content (text)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Scoring dimensions
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    returns_score: float = Field(default=0.0, ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, description="Final weighted score")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Usage tracking
    access_count: int = Field(default=0, ge=0)
    last_accessed_at: datetime | None = Field(default=None)

    # Optional outcome tracking
    outcome_summary: str | None = Field(default=None, description="Brief summary of outcome")


class DecisionOutcome(BaseModel):
    """Result/outcome of a trading decision."""

    model_config = {"extra": "forbid"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_id: str = Field(description="ID of the associated memory")
    decision: str = Field(description="Trading decision (BUY, SELL, HOLD)")

    entry_price: float = Field(description="Entry price")
    exit_price: float | None = Field(default=None, description="Exit price")
    pnl_amount: float | None = Field(default=None, description="Profit/Loss in currency")
    pnl_percent: float | None = Field(default=None, description="Profit/Loss percentage")

    confidence: int | None = Field(default=None, ge=0, le=100)
    time_horizon: str | None = Field(default=None, description="Time horizon (1d, 1w, 1m)")

    outcome_timestamp: datetime | None = Field(default=None)


class ReflectionSession(BaseModel):
    """A reflection cycle to review and update agent memories."""

    model_config = {"extra": "forbid"}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_type: str = Field(description="Type of reflection (scheduled, event_driven, manual)")

    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = Field(default=None)

    memories_reviewed: int = Field(default=0, ge=0)
    memories_updated: int = Field(default=0, ge=0)

    performance_metrics: dict[str, Any] = Field(default_factory=dict)
    insights: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    model_config = {"extra": "forbid"}

    agent_name: str
    query_context: str
    query_embedding: list[float]

    top_k: int = Field(default=5, ge=1, le=50)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    time_horizon: datetime | None = Field(default=None, description="Only retrieve memories after this time")
    memory_types: list[str] | None = Field(default=None, description="Filter by memory types")


class MemoryRetrievalConfig(BaseModel):
    """Configuration for memory retrieval scoring."""

    model_config = {"extra": "forbid"}

    # Weighting for composite score
    w_similarity: float = Field(default=0.5, ge=0.0, le=1.0, description="Semantic similarity weight")
    w_recency: float = Field(default=0.3, ge=0.0, le=1.0, description="Recency weight")
    w_returns: float = Field(default=0.2, ge=0.0, le=1.0, description="Historical returns weight")

    # Recency decay parameters
    recency_half_life_days: int = Field(default=30, ge=1, description="Half-life for recency decay")

    # Retrieval parameters
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=50)


class EmbeddingModelConfig(BaseModel):
    """Configuration for embedding model."""

    model_config = {"extra": "forbid"}

    model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    device: str = Field(default="cpu", description="cpu, cuda, mps")
    batch_size: int = Field(default=32, ge=1)
    normalize_embeddings: bool = Field(default=True)


class MemoryStats(BaseModel):
    """Statistics about agent memory database."""

    model_config = {"extra": "forbid"}

    agent_name: str
    total_memories: int

    # By memory type
    memories_by_type: dict[str, int] = Field(default_factory=dict)

    # Scoring averages
    avg_similarity_score: float = 0.0
    avg_recency_score: float = 0.0
    avg_returns_score: float = 0.0
    avg_composite_score: float = 0.0

    # Outcomes
    total_outcomes: int = 0
    avg_pnl: float = 0.0
    win_rate: float = 0.0

    # Timestamps
    oldest_memory: datetime | None = None
    newest_memory: datetime | None = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MemoryUpdate(BaseModel):
    """Update to be applied to a memory."""

    model_config = {"extra": "forbid"}

    memory_id: str

    # Scores to update
    similarity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    returns_score: float | None = Field(default=None, ge=0.0, le=1.0)
    composite_score: float | None = Field(default=None)

    # Metadata updates
    metadata: dict[str, Any] | None = Field(default=None)
    outcome_summary: str | None = Field(default=None)

    # Usage tracking
    increment_access_count: bool = Field(default=False)
