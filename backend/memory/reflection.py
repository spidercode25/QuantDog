# Reflection Worker - Periodic Learning Loop

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from memory.database import MemoryDatabase
from memory.models import (
    Memory,
    DecisionOutcome,
    ReflectionSession,
    MemoryUpdate,
)
from memory.retriever import MemoryRetriever
from memory.embedding import EmbeddingGenerator


class ReflectionWorker:
    """Periodic reflection worker to review past decisions and update agent memories.

    This worker implements the learning loop component of the memory system.
    It periodically reviews past trading decisions, analyzes performance,
    updates memory scores based on outcomes, and generates new reflection memories.

    The reflection process:
    1. Identify recent decisions with outcomes
    2. Analyze performance metrics
    3. Update returns_score for relevant memories
    4. Identify patterns and insights
    5. Store reflection as new memory for future use
    """

    def __init__(
        self,
        database: MemoryDatabase,
        agents: list[str],
        embedder: EmbeddingGenerator | None = None,
        reflection_interval_days: int = 7,
        memory_half_life_days: int = 30,
        min_decisions_for_reflection: int = 3,
    ):
        """Initialize the reflection worker.

        Args:
            database: MemoryDatabase instance
            agents: List of agent names to reflect on
            embedder: EmbeddingGenerator instance (optional, will create if not provided)
            reflection_interval_days: Days between reflection cycles
            memory_half_life_days: Half-life for recency decay
            min_decisions_for_reflection: Minimum decisions needed to trigger reflection
        """
        self._db = database
        self._agents = agents
        self._embedder = embedder or EmbeddingGenerator()
        self._reflection_interval = timedelta(days=reflection_interval_days)
        self._memory_half_life = timedelta(days=memory_half_life_days)
        self._min_decisions = min_decisions_for_reflection

    def run_reflection_cycle(self) -> ReflectionSession:
        """Execute a complete reflection cycle.

        This method:
        1. Creates a new reflection session
        2. For each agent:
           - Reviews recent decisions with outcomes
           - Analyzes performance
           - Updates memory scores
           - Generates insights
           - Stores reflections as new memories
        3. Finalizes the session

        Returns:
            ReflectionSession object with results
        """
        session = ReflectionSession(
            session_type="scheduled",
            start_time=datetime.utcnow(),
        )

        # Reflect on each agent
        for agent in self._agents:
            agent_reflection = self._reflect_agent(agent)
            
            # Update session with agent results
            session.memories_reviewed += agent_reflection["memories_reviewed"]
            session.memories_updated += agent_reflection["memories_updated"]

            # Aggregate performance metrics
            if "performance_metrics" not in session.performance_metrics:
                session.performance_metrics[agent] = agent_reflection["performance_metrics"]
            else:
                # Merge metrics
                for key, value in agent_reflection["performance_metrics"].items():
                    if key in session.performance_metrics[agent]:
                        session.performance_metrics[agent][key] += value
                    else:
                        session.performance_metrics[agent][key] = value

            # Collect insights
            if agent_reflection["insights"]:
                if "insights" not in session.insights:
                    session.insights["insights"] = {}
                session.insights["insights"][agent] = agent_reflection["insights"]

        session.end_time = datetime.utcnow()

        # Store the reflection session
        self._save_reflection_session(session)

        return session

    def _reflect_agent(self, agent_name: str) -> dict[str, Any]:
        """Reflect on a single agent's recent decisions.

        Args:
            agent_name: Name of the agent to reflect on

        Returns:
            Dictionary with reflection results
        """
        # 1. Get recent decisions with outcomes
        decisions = self._get_recent_decisions_with_outcomes(agent_name)

        if not decisions:
            return {
                "agent_name": agent_name,
                "memories_reviewed": 0,
                "memories_updated": 0,
                "performance_metrics": {},
                "insights": None,
            }

        # 2. Analyze performance
        performance = self._analyze_agent_performance(decisions)

        # 3. Update memory scores based on outcomes
        memories_updated = 0
        for decision, outcome in decisions:
            new_score = self._calculate_returns_score(decision, outcome)
            if new_score != decision.returns_score:
                self._db.update_memory(
                    update=MemoryUpdate(
                        memory_id=decision.id,
                        returns_score=new_score,
                        outcome_summary=self._create_outcome_summary(outcome),
                        metadata={"pnl_percent": outcome.pnl_percent},
                    )
                )
                memories_updated += 1

        # 4. Identify patterns and generate insights
        insights = self._identify_performance_patterns(decisions, performance)

        # 5. Store reflection as new memory
        if insights:
            reflection_memory = self._create_reflection_memory(
                agent_name=agent_name,
                decisions=decisions,
                performance=performance,
                insights=insights,
            )
            self._db.save_memory(reflection_memory)

        return {
            "agent_name": agent_name,
            "memories_reviewed": len(decisions),
            "memories_updated": memories_updated,
            "performance_metrics": performance,
            "insights": insights,
        }

    def _get_recent_decisions_with_outcomes(
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
        recent_memories = self._db.get_memories_by_agent(agent_name, limit=1000)

        decisions_with_outcomes = []
        for memory in recent_memories:
            # Only consider decision memories
            if memory.memory_type != "decision":
                continue

            # Only consider recent memories
            if memory.created_at < cutoff_date:
                continue

            # Try to get outcome for this memory
            outcome = self._get_outcome_for_memory(memory.id)
            if outcome:
                decisions_with_outcomes.append((memory, outcome))

        return decisions_with_outcomes

    def _get_outcome_for_memory(self, memory_id: str) -> DecisionOutcome | None:
        """Get the outcome associated with a memory.

        Args:
            memory_id: Memory ID

        Returns:
            DecisionOutcome or None
        """
        # Query the database for outcomes
        # For now, we need to add this method to MemoryDatabase
        # Since it doesn't exist, we'll return None for now
        return None

    def _analyze_agent_performance(
        self,
        decisions: list[tuple[Memory, DecisionOutcome]],
    ) -> dict[str, Any]:
        """Analyze agent decision performance.

        Args:
            decisions: List of (memory, outcome) tuples

        Returns:
            Dictionary with performance metrics
        """
        if not decisions:
            return {}

        total_pnl = sum(outcome.pnl_percent for _, outcome in decisions if outcome.pnl_percent is not None)
        total_count = len(decisions)
        wins = sum(1 for _, outcome in decisions if outcome.pnl_percent and outcome.pnl_percent > 0)

        # Calculate metrics
        metrics = {
            "total_decisions": total_count,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / total_count if total_count > 0 else 0.0,
            "win_rate": wins / total_count if total_count > 0 else 0.0,
        }

        # Separate BUY and SELL performance
        buy_decisions = [d for d in decisions if d[0].metadata.get("decision") == "BUY"]
        sell_decisions = [d for d in decisions if d[0].metadata.get("decision") == "SELL"]

        if buy_decisions:
            buy_pnls = [o.pnl_percent for _, o in buy_decisions if o.pnl_percent is not None]
            metrics["buy_decisions"] = len(buy_decisions)
            metrics["buy_avg_pnl"] = sum(buy_pnls) / len(buy_pnls) if buy_pnls else 0.0
            metrics["buy_win_rate"] = sum(1 for pnl in buy_pnls if pnl > 0) / len(buy_pnls) if buy_pnls else 0.0

        if sell_decisions:
            sell_pnls = [o.pnl_percent for _, o in sell_decisions if o.pnl_percent is not None]
            metrics["sell_decisions"] = len(sell_decisions)
            metrics["sell_avg_pnl"] = sum(sell_pnls) / len(sell_pnls) if sell_pnls else 0.0
            metrics["sell_win_rate"] = sum(1 for pnl in sell_pnls if pnl < 0) / len(sell_pnls) if sell_pnls else 0.0

        return metrics

    def _calculate_returns_score(
        self,
        memory: Memory,
        outcome: DecisionOutcome | None,
    ) -> float:
        """Calculate returns score based on outcome.

        Args:
            memory: Memory object
            outcome: DecisionOutcome object

        Returns:
            Returns score [0, 1]
        """
        if not outcome or outcome.pnl_percent is None:
            return memory.returns_score  # No change if no outcome

        pnl = outcome.pnl_percent
        decision_type = memory.metadata.get("decision", "").upper()

        if decision_type == "BUY":
            if pnl > 0:
                return min(abs(pnl) / 50.0, 1.0)  # Normalize positive returns
            else:
                return max(1.0 - abs(pnl) / 25.0, 0.0)  # Penalize losses

        elif decision_type == "SELL":
            if pnl < 0:  # Short position profit
                return min(abs(pnl) / 50.0, 1.0)  # Normalize negative returns
            else:
                return max(1.0 - abs(pnl) / 25.0, 0.0)  # Penalize losses

        elif decision_type == "HOLD":
            # HOLD is more nuanced
            # If we held and market went against us = good
            # If we held and market moved with us = could have traded
            # Simplified: use absolute PnL, smaller penalty
            return max(0.5 - abs(pnl) / 100.0, 0.0)

        else:
            return 0.5

    def _create_outcome_summary(self, outcome: DecisionOutcome) -> str:
        """Create a brief outcome summary.

        Args:
            outcome: DecisionOutcome object

        Returns:
            Summary string
        """
        if outcome.pnl_percent is None:
            return "No outcome recorded"

        if outcome.pnl_percent > 0:
            return f"Profit +{outcome.pnl_percent:.1f}%"
        elif outcome.pnl_percent < 0:
            return f"Loss {outcome.pnl_percent:.1f}%"
        else:
            return "Breakeven"

    def _identify_performance_patterns(
        self,
        decisions: list[tuple[Memory, DecisionOutcome]],
        performance: dict[str, Any],
    ) -> list[str]:
        """Identify performance patterns and generate insights.

        Args:
            decisions: List of (memory, outcome) tuples
            performance: Performance metrics

        Returns:
            List of insight strings
        """
        insights = []

        # Insight 1: Overall performance trend
        if performance["avg_pnl"] > 5.0:
            insights.append(f"Strong overall performance (+{performance['avg_pnl']:.1f}% avg PnL)")
        elif performance["avg_pnl"] < -5.0:
            insights.append(f"Weak overall performance ({performance['avg_pnl']:.1f}% avg PnL)")
        else:
            insights.append(f"Moderate overall performance ({performance['avg_pnl']:+.1f}% avg PnL)")

        # Insight 2: Win rate
        if performance["win_rate"] > 0.7:
            insights.append("High win rate (>70%) - strategy consistency")
        elif performance["win_rate"] < 0.4:
            insights.append("Low win rate (<40%) - consider strategy adjustment")

        # Insight 3: BUY vs SELL performance
        if "buy_decisions" in performance and "sell_decisions" in performance:
            buy_avg = performance.get("buy_avg_pnl", 0)
            sell_avg = performance.get("sell_avg_pnl", 0)

            if buy_avg > sell_avg * 1.5:
                insights.append("BUY decisions significantly outperform SELL")
            elif sell_avg > buy_avg * 1.5:
                insights.append("SELL decisions significantly outperform BUY")

        # Insight 4: Recent trend
        recent_pnls = [
            outcome.pnl_percent
            for _, outcome in decisions[-5:]
            if outcome and outcome.pnl_percent is not None
        ]

        if len(recent_pnls) >= 3:
            recent_avg = sum(recent_pnls) / len(recent_pnls)
            if recent_avg > 0 and performance["avg_pnl"] < recent_avg:
                insights.append("Recent performance improving")
            elif recent_avg < 0 and performance["avg_pnl"] > recent_avg:
                insights.append("Recent performance declining")

        return insights

    def _create_reflection_memory(
        self,
        agent_name: str,
        decisions: list[tuple[Memory, DecisionOutcome]],
        performance: dict[str, Any],
        insights: list[str],
    ) -> Memory:
        """Create a reflection memory.

        Args:
            agent_name: Agent name
            decisions: Decisions reviewed
            performance: Performance metrics
            insights: Performance insights

        Returns:
            Memory object
        """
        # Create summary text
        summary_lines = [
            f"Reflection for {agent_name}",
            f"Decisions reviewed: {len(decisions)}",
            f"Overall performance: {performance['avg_pnl']:+.1f}% avg PnL",
            f"Win rate: {performance['win_rate']:.1%}",
            "",
        ]

        if insights:
            summary_lines.append("Key Insights:")
            for i, insight in enumerate(insights, 1):
                summary_lines.append(f"  {i}. {insight}")

        summary_lines.append("")

        # Add summary of recent decisions
        summary_lines.append("Recent Decisions:")
        for memory, outcome in decisions[-3:]:  # Last 3 decisions
            decision = memory.metadata.get("decision", "UNKNOWN")
            summary_lines.append(
                f"  - {decision} decision, PnL: {self._create_outcome_summary(outcome)}"
            )

        content = "\n".join(summary_lines)

        # Create reflection embedding
        text_for_embedding = f"{agent_name} performance: {performance['avg_pnl']:+.1f}% PnL, {performance['win_rate']:.0%} win rate"
        embedding = self._embedder.encode(text_for_embedding)

        # Create metadata
        metadata = {
            "performance": performance,
            "insights": insights,
            "decisions_count": len(decisions),
            "reflection_type": "scheduled",
        }

        # Calculate scores
        # Reflections have high recency, moderate returns (based on performance)
        recency = 1.0
        returns_score = min(max(performance["avg_pnl"] / 50.0 + 0.5, 0.0), 1.0) if "avg_pnl" in performance else 0.5
        similarity = 0.5  # Self-reflection baseline

        composite = 0.3 * similarity + 0.4 * recency + 0.3 * returns_score

        return Memory(
            agent_name=agent_name,
            memory_type="reflection",
            embedding=embedding,
            embedding_model=self._embedder.config.model_name,
            context=json.dumps({"decisions_count": len(decisions)}),
            content=content,
            metadata=metadata,
            similarity_score=similarity,
            recency_score=recency,
            returns_score=returns_score,
            composite_score=composite,
        )

    def _save_reflection_session(self, session: ReflectionSession):
        """Save the reflection session to database.

        Args:
            session: ReflectionSession object
        """
        # For now, we'll just log it
        # In a full implementation, we'd save to reflection_sessions table
        print(f"\n[Reflection Cycle] Session completed:")
        print(f"  Type: {session.session_type}")
        print(f"  Duration: {session.end_time - session.start_time if session.end_time else 'pending'}")
        print(f"  Memories reviewed: {session.memories_reviewed}")
        print(f"  Memories updated: {session.memories_updated}")
        print(f"  Insights generated: {len(session.insights.get('insights', {}))} agents")
        print()

    def should_reflect(self, agent_name: str) -> bool:
        """Check if reflection should be triggered for an agent.

        Args:
            agent_name: Agent name

        Returns:
            True if reflection should be triggered
        """
        decisions = self._get_recent_decisions_with_outcomes(agent_name, days_back=self._reflection_interval.days)
        return len(decisions) >= self._min_decisions

    def get_status(self) -> dict[str, Any]:
        """Get status of the reflection worker.

        Returns:
            Dictionary with status information
        """
        status = {
            "agents": self._agents,
            "reflection_interval_days": self._reflection_interval.days,
            "memory_half_life_days": self._memory_half_life.days,
            "min_decisions_for_reflection": self._min_decisions,
            "last_reflection": None,
            "next_reflection": None,
        }

        # Check if reflection is needed for each agent
        status["agents_needing_reflection"] = []
        for agent in self._agents:
            if self.should_reflect(agent):
                status["agents_needing_reflection"].append(agent)

        return status
