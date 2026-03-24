# Agent with Memory Integration

from __future__ import annotations

import json
from typing import Any

from research.llm_client import LLMClient, AgentStatus
from memory import (
    Memory,
    MemoryDatabase,
    EmbeddingGenerator,
    MemoryRetriever,
    MemoryQuery,
    MemoryUpdate,
    MemoryRetrievalConfig,
)


class AgentWithMemory(LLMClient):
    """LLM Agent with persistent memory.

    This wrapper adds memory capabilities to existing LLM implementations.
    It retrieves relevant historical experiences before making decisions
    and stores new decisions for future reference.

    Workflow:
    1. Pre-execution: Retrieve similar memories from database
    2. Context injection: Format memories and inject into prompt
    3. Execution: Call underlying LLM client
    4. Post-execution: Store decision as new memory
    """

    def __init__(
        self,
        base_client: LLMClient,
        agent_name: str,
        memory_db: MemoryDatabase,
        embedder: EmbeddingGenerator | None = None,
        retrieval_config: MemoryRetrievalConfig | None = None,
        use_memory: bool = True,
    ):
        """Initialize agent with memory.

        Args:
            base_client: Underlying LLM client to wrap
            agent_name: Unique name for this agent
            memory_db: Memory database instance
            embedder: Embedding generator (optional, will create if not provided)
            retrieval_config: Memory retrieval configuration
            use_memory: Whether to use memory (can be toggled)
        """
        self._base_client = base_client
        self._agent_name = agent_name
        self._memory_db = memory_db
        self._embedder = embedder or EmbeddingGenerator()
        self._retrieval_config = retrieval_config or MemoryRetrievalConfig()
        self._retriever = MemoryRetriever(
            database=memory_db,
            config=retrieval_config,
            embedder=self._embedder,
        )
        self._use_memory = use_memory

    @property
    def agent_name(self) -> str:
        """Get the agent name."""
        return self._agent_name

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Execute LLM completion with memory.

        Args:
            system_prompt: System instruction
            user_prompt: User prompt
            response_schema: Pydantic model to validate against
            timeout_seconds: Request timeout

        Returns:
            Tuple of (validated_output_dict, status, model_id or None)
        """
        # 1. Retrieve relevant memories if enabled
        memories_used = []
        if self._use_memory:
            query_embedding = self._embedder.encode(user_prompt)

            query = MemoryQuery(
                agent_name=self._agent_name,
                query_context=user_prompt,
                query_embedding=query_embedding,
                top_k=self._retrieval_config.top_k,
                min_confidence=self._retrieval_config.similarity_threshold,
            )

            memories_used = self._retriever.retrieve(query)

        # 2. Inject memories into context
        enhanced_prompt = user_prompt
        if memories_used:
            memory_context = self._format_memories(memories_used)
            enhanced_prompt = f"{memory_context}\n\n{user_prompt}"

        # 3. Execute underlying LLM client
        output, status, model_id = self._base_client.complete(
            system_prompt=system_prompt,
            user_prompt=enhanced_prompt,
            response_schema=response_schema,
            timeout_seconds=timeout_seconds,
        )

        # 4. Store decision as memory if successful
        if status == AgentStatus.OK:
            self._store_memory(
                context=user_prompt,
                output=output,
                memories_used=memories_used,
                query_embedding=self._embedder.encode(user_prompt),
                system_prompt=system_prompt,
            )

        return output, status, model_id

    def is_available(self) -> bool:
        """Check if the agent is available."""
        return self._base_client.is_available()

    def _format_memories(self, memories: list[Memory]) -> str:
        """Format retrieved memories into context string.

        Args:
            memories: List of Memory objects

        Returns:
            Formatted context string
        """
        if not memories:
            return ""

        lines = [
            "### Relevant Past Experiences ###",
            "",
        ]

        for i, memory in enumerate(memories, 1):
            lines.append(f"[Experience {i}] {memory.content}")

            if memory.outcome_summary:
                lines.append(f"Outcome: {memory.outcome_summary}")

            lines.extend([
                f"Similarity: {memory.similarity_score:.2f}",
                f"Recency: {memory.recency_score:.2f}",
                f"Returns Score: {memory.returns_score:.2f}",
                f"Composite Score: {memory.composite_score:.2f}",
                "",
            ])

        lines.append("### End Past Experiences ###")

        return "\n".join(lines)

    def _store_memory(
        self,
        context: str,
        output: dict[str, Any],
        memories_used: list[Memory],
        query_embedding: list[float],
        system_prompt: str = "",
    ):
        """Store the decision as a new memory.

        Args:
            context: Original query context
            output: LLM output
            memories_used: Memories that were retrieved
            query_embedding: Query embedding
            system_prompt: System prompt used
        """
        # Create content summary
        content = self._create_content_summary(context, output)

        # Create metadata
        metadata = {
            "decision": output.get("decision", "UNKNOWN"),
            "confidence": output.get("confidence", 0),
            "system_prompt_length": len(system_prompt),
            "context_length": len(context),
            "memories_used_count": len(memories_used),
            "memories_used_ids": [m.id for m in memories_used],
        }

        # Add output-specific metadata
        if "key_factors" in output:
            metadata["key_factors"] = output["key_factors"]
        if "reasoning" in output:
            metadata["reasoning"] = output["reasoning"]
        if "signal" in output:
            metadata["signal"] = output["signal"]
        if "trend_summary" in output:
            metadata["trend_summary"] = output["trend_summary"]

        # Calculate composite score
        recency = 1.0  # New memories have high recency
        returns = 0.0  # Unknown until outcome recorded
        similarity = 0.0  # Self-similarity

        composite = (
            self._retrieval_config.w_similarity * similarity +
            self._retrieval_config.w_recency * recency +
            self._retrieval_config.w_returns * returns
        )

        memory = Memory(
            agent_name=self._agent_name,
            memory_type="decision",
            embedding=query_embedding,
            embedding_model=self._embedder.config.model_name,
            context=context,
            content=content,
            metadata=metadata,
            similarity_score=similarity,
            recency_score=recency,
            returns_score=returns,
            composite_score=composite,
        )

        # Save to database
        self._memory_db.save_memory(memory)

    def _create_content_summary(self, context: str, output: dict[str, Any]) -> str:
        """Create a content summary from context and output.

        Args:
            context: Original context
            output: LLM output

        Returns:
            Summary string
        """
        # Start with decision
        decision = output.get("decision", "UNKNOWN")
        summary = f"Decision: {decision}"

        # Add confidence
        confidence = output.get("confidence")
        if confidence:
            summary += f" (Confidence: {confidence}%)"

        # Add reasoning if available
        reasoning = output.get("reasoning")
        if reasoning and len(reasoning) > 0:
            summary += f"\nReasoning: {reasoning[:200]}"  # Limit to 200 chars

        # Add key factors if available
        key_factors = output.get("key_factors", [])
        if key_factors:
            summary += f"\nKey Factors: {', '.join(key_factors[:3])}"

        return summary

    def record_outcome(
        self,
        memory_id: str,
        entry_price: float,
        exit_price: float | None = None,
        pnl_amount: float | None = None,
        pnl_percent: float | None = None,
    ):
        """Record the outcome of a decision.

        Args:
            memory_id: Memory ID to update
            entry_price: Entry price
            exit_price: Exit price (if position closed)
            pnl_amount: Profit/Loss in currency
            pnl_percent: Profit/Loss percentage
        """
        from memory import DecisionOutcome

        outcome = DecisionOutcome(
            memory_id=memory_id,
            decision="UNKNOWN",  # Will be filled from memory metadata
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_amount=pnl_amount,
            pnl_percent=pnl_percent,
        )

        # Save outcome
        self._memory_db.save_decision_outcome(outcome)

        # Update memory score based on outcome
        if pnl_percent is not None:
            # Calculate returns score
            returns_score = self._calculate_returns_score_from_pnl(pnl_percent)

            self._memory_db.update_memory(
                update=MemoryUpdate(
                    memory_id=memory_id,
                    returns_score=returns_score,
                )
            )

    def _calculate_returns_score_from_pnl(self, pnl_percent: float) -> float:
        """Calculate returns score from PnL percentage."""
        # Get the decision type from memory
        memory = self._memory_db.get_memory(self._last_memory_id)
        if not memory:
            return 0.5

        decision_type = memory.metadata.get("decision", "").upper()

        if decision_type == "BUY":
            if pnl_percent > 0:
                return min(pnl_percent / 50.0, 1.0)
            else:
                return 0.0
        elif decision_type == "SELL":
            if pnl_percent < 0:
                return min(abs(pnl_percent) / 50.0, 1.0)
            else:
                return 0.0
        else:
            return 0.5

    def toggle_memory(self, use: bool):
        """Toggle memory usage.

        Args:
            use: Whether to use memory
        """
        self._use_memory = use

    def get_memory_stats(self):
        """Get statistics about agent's memory.

        Returns:
            MemoryStats object
        """
        return self._memory_db.get_memory_stats(self._agent_name)

    def explain_last_retrieval(self) -> dict[str, Any] | None:
        """Explain the last memory retrieval (for debugging).

        Returns:
            Dictionary with explanation or None if no retrieval occurred
        """
        if not hasattr(self, "_last_memories_used") or not self._last_memories_used:
            return None

        explanations = []
        for memory in self._last_memories_used:
            explanations.append(self._retriever.explain_scores(memory))

        return {
            "agent_name": self._agent_name,
            "memories_retrieved": len(explanations),
            "explanations": explanations,
        }
