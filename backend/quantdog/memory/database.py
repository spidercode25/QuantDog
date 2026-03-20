# Memory Database Layer

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from quantdog.infra.sqlalchemy import get_engine
from quantdog.memory.models import (
    Memory,
    DecisionOutcome,
    ReflectionSession,
    MemoryUpdate,
    MemoryStats,
)
from sqlalchemy import text


class MemoryDatabase:
    """Database layer for agent memories using SQLite.

    This class provides CRUD operations for storing and retrieving
    agent memories, decision outcomes, and reflection sessions.

    All data is stored locally in SQLite for privacy and portability.
    """

    def __init__(self, database_url: str):
        """Initialize the memory database.

        Args:
            database_url: SQLAlchemy database URL (e.g., sqlite:///memory.db)
        """
        self._database_url = database_url
        self._engine = get_engine(database_url)

    def create_tables(self):
        """Create memory tables if they don't exist."""
        with self._engine.connect() as conn:
            # Create agent_memories table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_memories (
                    id TEXT PRIMARY KEY NOT NULL,
                    agent_name TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    context TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    similarity_score REAL DEFAULT 0.0,
                    recency_score REAL DEFAULT 0.0,
                    returns_score REAL DEFAULT 0.0,
                    composite_score REAL DEFAULT 0.0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at DATETIME,
                    outcome_summary TEXT
                )
            """))

            # Create decision_outcomes table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    id TEXT PRIMARY KEY NOT NULL,
                    memory_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    pnl_amount REAL,
                    pnl_percent REAL,
                    confidence INTEGER,
                    time_horizon TEXT,
                    outcome_timestamp DATETIME,
                    FOREIGN KEY (memory_id) REFERENCES agent_memories(id)
                )
            """))

            # Create reflection_sessions table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reflection_sessions (
                    id TEXT PRIMARY KEY NOT NULL,
                    session_type TEXT NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    memories_reviewed INTEGER DEFAULT 0,
                    memories_updated INTEGER DEFAULT 0,
                    performance_metrics TEXT,
                    insights TEXT
                )
            """))

            # Create indexes for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_name
                ON agent_memories(agent_name)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_memories_created_at
                ON agent_memories(created_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_memories_composite_score
                ON agent_memories(composite_score)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_decision_outcomes_memory_id
                ON decision_outcomes(memory_id)
            """))

            conn.commit()

    def save_memory(self, memory: Memory) -> str:
        """Save a memory to the database.

        Args:
            memory: Memory object to save

        Returns:
            Memory ID
        """
        with self._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO agent_memories
                    (id, agent_name, memory_type, embedding, embedding_model, context, content,
                     metadata, similarity_score, recency_score, returns_score, composite_score,
                     created_at, updated_at, access_count, last_accessed_at, outcome_summary)
                    VALUES
                    (:id, :agent_name, :memory_type, :embedding, :embedding_model, :context, :content,
                     :metadata, :similarity_score, :recency_score, :returns_score, :composite_score,
                     :created_at, :updated_at, :access_count, :last_accessed_at, :outcome_summary)
                """),
                {
                    "id": memory.id,
                    "agent_name": memory.agent_name,
                    "memory_type": memory.memory_type,
                    "embedding": json.dumps(memory.embedding),
                    "embedding_model": memory.embedding_model,
                    "context": memory.context,
                    "content": memory.content,
                    "metadata": json.dumps(memory.metadata),
                    "similarity_score": memory.similarity_score,
                    "recency_score": memory.recency_score,
                    "returns_score": memory.returns_score,
                    "composite_score": memory.composite_score,
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                    "access_count": memory.access_count,
                    "last_accessed_at": memory.last_accessed_at,
                    "outcome_summary": memory.outcome_summary,
                },
            )
            conn.commit()

        return memory.id

    def get_memory(self, memory_id: str) -> Memory | None:
        """Get a memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory object or None
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, agent_name, memory_type, embedding, embedding_model, context, content,
                           metadata, similarity_score, recency_score, returns_score, composite_score,
                           created_at, updated_at, access_count, last_accessed_at, outcome_summary
                    FROM agent_memories
                    WHERE id = :memory_id
                """),
                {"memory_id": memory_id},
            )
            row = result.fetchone()

        if not row:
            return None

        return self._row_to_memory(row)

    def get_memories_by_agent(
        self,
        agent_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        """Get memories for a specific agent.

        Args:
            agent_name: Agent name
            limit: Maximum number of memories to return
            offset: Offset for pagination

        Returns:
            List of Memory objects
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, agent_name, memory_type, embedding, embedding_model, context, content,
                           metadata, similarity_score, recency_score, returns_score, composite_score,
                           created_at, updated_at, access_count, last_accessed_at, outcome_summary
                    FROM agent_memories
                    WHERE agent_name = :agent_name
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"agent_name": agent_name, "limit": limit, "offset": offset},
            )
            rows = result.fetchall()

        return [self._row_to_memory(row) for row in rows]

    def update_memory(self, update: MemoryUpdate):
        """Update a memory.

        Args:
            update: MemoryUpdate object with fields to update
        """
        updates = {}
        if update.similarity_score is not None:
            updates["similarity_score"] = update.similarity_score
        if update.recency_score is not None:
            updates["recency_score"] = update.recency_score
        if update.returns_score is not None:
            updates["returns_score"] = update.returns_score
        if update.composite_score is not None:
            updates["composite_score"] = update.composite_score
        if update.metadata is not None:
            updates["metadata"] = json.dumps(update.metadata)
        if update.outcome_summary is not None:
            updates["outcome_summary"] = update.outcome_summary

        updates["updated_at"] = datetime.utcnow()

        if update.increment_access_count:
            updates["last_accessed_at"] = datetime.utcnow()

        if not updates:
            return

        with self._engine.connect() as conn:
            # Build update SQL dynamically
            set_clauses = ", ".join([f"{k} = :{k}" for k in updates.keys()])
            sql = f"""
                UPDATE agent_memories
                SET {set_clauses},
                    access_count = CASE WHEN :increment_access_count
                        THEN access_count + 1
                        ELSE access_count
                    END
                WHERE id = :memory_id
            """

            params = {**updates, "memory_id": update.memory_id, "increment_access_count": update.increment_access_count}
            conn.execute(text(sql), params)
            conn.commit()

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted, False if not found
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM agent_memories WHERE id = :memory_id"),
                {"memory_id": memory_id},
            )
            conn.commit()

        return result.rowcount > 0

    def search_similar_memories(
        self,
        agent_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        min_threshold: float = 0.0,
    ) -> list[Memory]:
        """Search for memories similar to a query embedding.

        This method fetches all memories for the agent and computes
        cosine similarity on the client side. For production with
        large datasets, consider using sqlite3-vss or ChromaDB.

        Args:
            agent_name: Agent name
            query_embedding: Query embedding vector
            top_k: Maximum number of results
            min_threshold: Minimum similarity threshold

        Returns:
            List of similar memories
        """
        # Fetch all memories for the agent
        memories = self.get_memories_by_agent(agent_name, limit=10000)

        # Compute similarities
        from quantdog.memory.embedding import EmbeddingGenerator
        embedder = EmbeddingGenerator()

        memories_with_score = []
        for memory in memories:
            similarity = embedder.similarity(query_embedding, memory.embedding)

            # Update similarity score in memory
            memory.similarity_score = similarity

            if similarity >= min_threshold:
                memories_with_score.append((memory, similarity))

        # Sort by similarity and return top_k
        memories_with_score.sort(key=lambda x: x[1], reverse=True)

        return [m for m, _ in memories_with_score[:top_k]]

    def save_decision_outcome(self, outcome: DecisionOutcome) -> str:
        """Save a decision outcome.

        Args:
            outcome: DecisionOutcome object

        Returns:
            Outcome ID
        """
        with self._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO decision_outcomes
                    (id, memory_id, decision, entry_price, exit_price, pnl_amount, pnl_percent,
                     confidence, time_horizon, outcome_timestamp)
                    VALUES
                    (:id, :memory_id, :decision, :entry_price, :exit_price, :pnl_amount, :pnl_percent,
                     :confidence, :time_horizon, :outcome_timestamp)
                """),
                {
                    "id": outcome.id,
                    "memory_id": outcome.memory_id,
                    "decision": outcome.decision,
                    "entry_price": outcome.entry_price,
                    "exit_price": outcome.exit_price,
                    "pnl_amount": outcome.pnl_amount,
                    "pnl_percent": outcome.pnl_percent,
                    "confidence": outcome.confidence,
                    "time_horizon": outcome.time_horizon,
                    "outcome_timestamp": outcome.outcome_timestamp,
                },
            )
            conn.commit()

        return outcome.id

    def get_outcome(self, outcome_id: str) -> DecisionOutcome | None:
        """Get a decision outcome by ID.

        Args:
            outcome_id: Outcome ID

        Returns:
            DecisionOutcome object or None
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, memory_id, decision, entry_price, exit_price, pnl_amount, pnl_percent,
                           confidence, time_horizon, outcome_timestamp
                    FROM decision_outcomes
                    WHERE id = :outcome_id
                """),
                {"outcome_id": outcome_id},
            )
            row = result.fetchone()

        if not row:
            return None

        return DecisionOutcome(
            id=row[0],
            memory_id=row[1],
            decision=row[2],
            entry_price=row[3],
            exit_price=row[4],
            pnl_amount=row[5],
            pnl_percent=row[6],
            confidence=row[7],
            time_horizon=row[8],
            outcome_timestamp=row[9],
        )

    def get_memory_stats(self, agent_name: str) -> MemoryStats:
        """Get statistics about an agent's memory database.

        Args:
            agent_name: Agent name

        Returns:
            MemoryStats object
        """

    def get_outcomes_for_memory_id(self, memory_id: str) -> list[DecisionOutcome]:
        """Get all outcomes for a specific memory.

        Args:
            memory_id: Memory ID

        Returns:
            List of DecisionOutcome objects
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, memory_id, decision, entry_price, exit_price, pnl_amount, pnl_percent,
                           confidence, time_horizon, outcome_timestamp
                    FROM decision_outcomes
                    WHERE memory_id = :memory_id
                """),
                {"memory_id": memory_id},
            )
            rows = result.fetchall()

        if not rows:
            return []

        return [
            DecisionOutcome(
                id=row[0],
                memory_id=row[1],
                decision=row[2],
                entry_price=row[3],
                exit_price=row[4],
                pnl_amount=row[5],
                pnl_percent=row[6],
                confidence=row[7],
                time_horizon=row[8],
                outcome_timestamp=row[9],
            )
            for row in rows
        ]

    def recent_decisions_with_outcomes(
        self,
        agent_name: str,
        days_back: int = 30,
    ) -> list[tuple[Memory, DecisionOutcome]]:
        """Get recent decisions with their outcomes.

        Args:
            agent_name: Agent name
            days_back: How many days back to look

        Returns:
            List of (memory, outcome) tuples
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        recent_memories = self.get_memories_by_agent(agent_name, limit=1000)

        decisions_with_outcomes = []
        for memory in recent_memories:
            # Only consider decision memories
            if memory.memory_type != "decision":
                continue

            # Only consider recent memories
            if memory.created_at < cutoff_date:
                continue

            # Get outcomes for this memory
            outcomes = self.get_outcomes_for_memory_id(memory.id)
            if outcomes:
                for outcome in outcomes:
                    decisions_with_outcomes.append((memory, outcome))

        return decisions_with_outcomes
        with self._engine.connect() as conn:
            # Total memories
            result = conn.execute(
                text("SELECT COUNT(*) FROM agent_memories WHERE agent_name = :agent_name"),
                {"agent_name": agent_name},
            )
            total_memories = result.fetchone()[0]

            # By memory type
            result = conn.execute(
                text("""
                    SELECT memory_type, COUNT(*)
                    FROM agent_memories
                    WHERE agent_name = :agent_name
                    GROUP BY memory_type
                """),
                {"agent_name": agent_name},
            )
            memories_by_type = {row[0]: row[1] for row in result.fetchall()}

            # Score averages
            result = conn.execute(
                text("""
                    SELECT AVG(similarity_score), AVG(recency_score), AVG(returns_score), AVG(composite_score)
                    FROM agent_memories
                    WHERE agent_name = :agent_name
                """),
                {"agent_name": agent_name},
            )
            row = result.fetchone()
            avg_similarity_score = row[0] or 0.0
            avg_recency_score = row[1] or 0.0
            avg_returns_score = row[2] or 0.0
            avg_composite_score = row[3] or 0.0

            # Outcomes
            result = conn.execute(
                text("""
                    SELECT COUNT(*), AVG(pnl_percent),
                           SUM(CASE WHEN pnl_percent > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)
                    FROM decision_outcomes
                    WHERE memory_id IN (SELECT id FROM agent_memories WHERE agent_name = :agent_name)
                """),
                {"agent_name": agent_name},
            )
            row = result.fetchone()
            total_outcomes = row[0] or 0
            avg_pnl = row[1] or 0.0
            win_rate = row[2] or 0.0

            # Timestamps
            result = conn.execute(
                text("""
                    SELECT MIN(created_at), MAX(created_at)
                    FROM agent_memories
                    WHERE agent_name = :agent_name
                """),
                {"agent_name": agent_name},
            )
            row = result.fetchone()
            oldest_memory = row[0]
            newest_memory = row[1]

        return MemoryStats(
            agent_name=agent_name,
            total_memories=total_memories,
            memories_by_type=memories_by_type,
            avg_similarity_score=avg_similarity_score,
            avg_recency_score=avg_recency_score,
            avg_returns_score=avg_returns_score,
            avg_composite_score=avg_composite_score,
            total_outcomes=total_outcomes,
            avg_pnl=avg_pnl,
            win_rate=win_rate,
            oldest_memory=oldest_memory,
            newest_memory=newest_memory,
            last_updated=datetime.utcnow(),
        )

    def _row_to_memory(self, row: tuple) -> Memory:
        """Convert database row to Memory object."""
        return Memory(
            id=row[0],
            agent_name=row[1],
            memory_type=row[2],
            embedding=json.loads(row[3]),
            embedding_model=row[4],
            context=row[5],
            content=row[6],
            metadata=json.loads(row[7]),
            similarity_score=row[8],
            recency_score=row[9],
            returns_score=row[10],
            composite_score=row[11],
            created_at=row[12],
            updated_at=row[13],
            access_count=row[14],
            last_accessed_at=row[15],
            outcome_summary=row[16],
        )
