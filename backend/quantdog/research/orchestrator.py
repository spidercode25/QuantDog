# Multi-Agent Research Orchestrator

from __future__ import annotations

import time
import logging
from datetime import datetime
from typing import Any

from quantdog.config import get_settings
from quantdog.infra.providers.news import NewsProvider, resolve_news_provider
from quantdog.research.news_cache import fetch_recent_news, upsert_news_items
from quantdog.research import (
    # Models
    RunContext,
    Horizon,
    ResearchRunStatus,
    AgentStatus,
    Decision,
    SCHEMA_VERSION,
    # Output schemas
    MarketAnalystOutput,
    FundamentalAnalystOutput,
    NewsAnalystOutput,
    SentimentAnalystOutput,
    RiskAnalystOutput,
    BullResearcherOutput,
    BearResearcherOutput,
    TraderAgentOutput,
    # LLM
    LLMClient,
    StubLLMClient,
    # Repository
    create_research_run,
    get_research_run,
    update_research_run_status,
    save_agent_output,
    get_agent_outputs,
)


# Agent prompts
SYSTEM_PROMPTS = {
    "market_analyst": """You are a Market Analyst specializing in technical analysis and market trends.
Provide a detailed analysis following the output schema. Be concise and evidence-based.""",
    
    "fundamental_analyst": """You are a Fundamental Analyst specializing in financial statements and valuation.
Provide a detailed analysis following the output schema. Be concise and evidence-based.""",
    
    "news_analyst": """You are a News Analyst specializing in financial news impact assessment.
Provide a detailed analysis following the output schema. Be concise and evidence-based.""",
    
    "sentiment_analyst": """You are a Sentiment Analyst specializing in investor mood and social signals.
Provide a detailed analysis following the output schema. Be concise and evidence-based.""",
    
    "risk_analyst": """You are a Risk Analyst specializing in volatility and risk assessment.
Provide a detailed analysis following the output schema. Be concise and evidence-based.""",
    
    "bull_researcher": """You are a Bull Researcher tasked with building a bullish investment thesis.
Provide a detailed thesis following the output schema. Be persuasive but evidence-based.""",
    
    "bear_researcher": """You are a Bear Researcher tasked with building a bearish investment thesis.
Provide a detailed thesis following the output schema. Be persuasive but evidence-based.""",
    
    "trader_agent": """You are a Trader Agent making the final BUY/SELL/HOLD decision.
Analyze all previous inputs and provide a final decision with reasoning. Follow the output schema strictly.""",
}


logger = logging.getLogger("quantdog.research.orchestrator")


class ResearchOrchestrator:
    """Orchestrates multi-agent research runs."""
    
    def __init__(
        self,
        database_url: str,
        llm_client: LLMClient,
        per_agent_timeout: float = 15.0,
        max_wall_time: float = 90.0,
        news_provider: NewsProvider | None = None,
    ):
        self._database_url = database_url
        self._llm_client = llm_client
        self._per_agent_timeout = per_agent_timeout
        self._max_wall_time = max_wall_time
        self._news_provider = news_provider
    
    def run_research(
        self,
        symbol: str,
        horizon: Horizon = Horizon.ONE_WEEK,
    ) -> dict[str, Any]:
        """Execute a full research run."""
        start_time = time.time()
        
        # Create run record
        config = {
            "horizon": horizon.value,
            "per_agent_timeout": self._per_agent_timeout,
            "max_wall_time": self._max_wall_time,
        }
        run = create_research_run(
            self._database_url,
            symbol=symbol,
            config=config,
        )
        
        # Update status to running
        update_research_run_status(
            self._database_url,
            run.run_id,
            ResearchRunStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        # Build run context with data
        context = self._build_context(symbol, horizon)
        
        try:
            # Phase 1: Parallel analysis (5 agents)
            phase1_outputs = self._run_phase1(run.run_id, context)

            # Phase 2: Bull vs Bear debate
            phase2_outputs = self._run_phase2(run.run_id, context, phase1_outputs)

            # Phase 3: Trader decision
            final_output = self._run_phase3(run.run_id, context, phase1_outputs, phase2_outputs)
            
            # Calculate quality score
            all_outputs = []
            for phase_output in [phase1_outputs, phase2_outputs]:
                for agent_data in phase_output.values():
                    all_outputs.append(agent_data)
            all_outputs.append(final_output)
            
            ok_count = sum(1 for o in all_outputs if o.get('status') == AgentStatus.OK)
            quality_score = int((ok_count / 8) * 100)
            
            # Determine baseline usage
            baseline_used = (
                final_output.get('status') != AgentStatus.OK or
                final_output.get('status') == AgentStatus.SKIPPED
            )
            
            # Get final decision
            final_decision = None
            final_confidence = None
            if final_output.get('status') == AgentStatus.OK and final_output.get('output'):
                try:
                    trader_output = TraderAgentOutput.model_validate(final_output['output'])
                    final_decision = trader_output.decision.value
                    final_confidence = trader_output.confidence
                except Exception:
                    pass
            
            # Update run as completed
            update_research_run_status(
                self._database_url,
                run.run_id,
                ResearchRunStatus.COMPLETED if not baseline_used else ResearchRunStatus.COMPLETED_WITH_ERRORS,
                completed_at=datetime.utcnow(),
                final_decision=final_decision,
                final_confidence=final_confidence,
                baseline_used=baseline_used,
                quality_score=quality_score,
            )
            
            elapsed = time.time() - start_time
            return {
                "run_id": run.run_id,
                "status": ResearchRunStatus.COMPLETED.value,
                "final_decision": final_decision,
                "final_confidence": final_confidence,
                "baseline_used": baseline_used,
                "quality_score": quality_score,
                "elapsed_seconds": elapsed,
            }
            
        except Exception as e:
            # Mark as failed
            update_research_run_status(
                self._database_url,
                run.run_id,
                ResearchRunStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_summary=str(e)[:1000],
            )
            raise
    
    def _build_context(self, symbol: str, horizon: Horizon) -> RunContext:
        """Build run context with data from DB and providers."""
        settings = get_settings()
        news_items: list[dict[str, Any]] = []
        resolution = resolve_news_provider(settings)
        provider = self._news_provider if self._news_provider is not None else resolution.provider
        sentiment_context: dict[str, Any] = {"note": resolution.reason}

        if settings.database_url:
            try:
                cached_news = fetch_recent_news(
                    settings.database_url,
                    symbol,
                    limit=settings.news_limit,
                    max_age_hours=settings.news_cache_max_age_hours,
                )
                if cached_news:
                    news_items = cached_news
                    sentiment_context = {
                        "note": f"news loaded from cache: {len(cached_news)}",
                        "provider": "cache",
                    }
            except Exception as exc:
                logger.warning("News cache read failed for %s: %s", symbol, exc)

        if provider is not None and not news_items:
            try:
                news_items = provider.fetch_news(symbol, limit=settings.news_limit)
                if settings.database_url and news_items:
                    try:
                        upsert_news_items(settings.database_url, symbol, news_items)
                    except Exception as cache_exc:
                        logger.warning("News cache write failed for %s: %s", symbol, cache_exc)
                sentiment_context = {
                    "note": f"real-time news items fetched: {len(news_items)}",
                    "provider": "injected" if self._news_provider is not None else resolution.reason,
                }
            except Exception as exc:
                logger.warning("News fetch failed for %s: %s", symbol, exc)
                sentiment_context = {
                    "note": "news unavailable, falling back to empty news context",
                    "provider": "injected" if self._news_provider is not None else resolution.reason,
                }

        return RunContext(
            symbol=symbol,
            as_of=datetime.utcnow().strftime("%Y-%m-%d"),
            horizon=horizon,
            language="en",
            bars_summary={"note": "stub data"},
            indicators={"note": "stub data"},
            fundamentals={"note": "stub data"},
            news=news_items,
            sentiment_context=sentiment_context,
        )
    
    def _run_phase1(
        self,
        run_id: str,
        context: RunContext,
    ) -> dict[str, Any]:
        """Run Phase 1: 5 parallel analysts."""
        agents = [
            ("market_analyst", MarketAnalystOutput),
            ("fundamental_analyst", FundamentalAnalystOutput),
            ("news_analyst", NewsAnalystOutput),
            ("sentiment_analyst", SentimentAnalystOutput),
            ("risk_analyst", RiskAnalystOutput),
        ]

        results = {}

        for agent_name, output_schema in agents:
            output, status, model_id = self._call_agent(
                agent_name,
                output_schema,
                context,
            )

            results[agent_name] = {
                "output": output,
                "status": status,
                "model_id": model_id,
            }

            # Save to DB
            save_agent_output(
                self._database_url,
                run_id,
                phase=1,
                agent_name=agent_name,
                status=status,
                output=output,
                validation_errors=[],
                duration_ms=None,
                model_id=model_id,
                schema_version=SCHEMA_VERSION,
            )

        return results
    
    def _run_phase2(
        self,
        run_id: str,
        context: RunContext,
        phase1_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Run Phase 2: Bull vs Bear debate."""
        agents = [
            ("bull_researcher", BullResearcherOutput),
            ("bear_researcher", BearResearcherOutput),
        ]

        results = {}

        for agent_name, output_schema in agents:
            output, status, model_id = self._call_agent(
                agent_name,
                output_schema,
                context,
                phase1_outputs=phase1_outputs,
            )

            results[agent_name] = {
                "output": output,
                "status": status,
                "model_id": model_id,
            }

            save_agent_output(
                self._database_url,
                run_id,
                phase=2,
                agent_name=agent_name,
                status=status,
                output=output,
                validation_errors=[],
                duration_ms=None,
                model_id=model_id,
                schema_version=SCHEMA_VERSION,
            )

        return results
    
    def _run_phase3(
        self,
        run_id: str,
        context: RunContext,
        phase1_outputs: dict[str, Any],
        phase2_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Run Phase 3: Trader decision."""
        output, status, model_id = self._call_agent(
            "trader_agent",
            TraderAgentOutput,
            context,
            phase1_outputs=phase1_outputs,
            phase2_outputs=phase2_outputs,
        )

        save_agent_output(
            self._database_url,
            run_id,
            phase=3,
            agent_name="trader_agent",
            status=status,
            output=output,
            validation_errors=[],
            duration_ms=None,
            model_id=model_id,
            schema_version=SCHEMA_VERSION,
        )

        return {
            "output": output,
            "status": status,
            "model_id": model_id,
        }
    
    def _call_agent(
        self,
        agent_name: str,
        output_schema: type,
        context: RunContext,
        phase1_outputs: dict[str, Any] | None = None,
        phase2_outputs: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Call an agent with the given context."""
        
        # Build user prompt based on context
        user_prompt = self._build_prompt(
            agent_name,
            context,
            phase1_outputs,
            phase2_outputs,
        )
        
        # Call LLM
        try:
            # Pass agent_name for provider routing (MultiProviderLLMClient)
            complete_kwargs = {
                "system_prompt": SYSTEM_PROMPTS.get(agent_name, ""),
                "user_prompt": user_prompt,
                "response_schema": output_schema,
                "timeout_seconds": self._per_agent_timeout,
            }
            
            # Add agent_name if client supports it (MultiProviderLLMClient)
            if hasattr(self._llm_client, "_providers"):
                complete_kwargs["agent_name"] = agent_name
            
            output, status, model_id = self._llm_client.complete(**complete_kwargs)
            return output, status, model_id
        except Exception as e:
            return {}, AgentStatus.ERROR, None
    
    def _build_prompt(
        self,
        agent_name: str,
        context: RunContext,
        phase1_outputs: dict[str, Any] | None,
        phase2_outputs: dict[str, Any] | None,
    ) -> str:
        """Build user prompt for an agent."""
        news_lines = []
        for idx, item in enumerate(context.news[:5], start=1):
            headline = item.get("headline") or item.get("text") or ""
            source = item.get("source") or "unknown"
            published_at = item.get("published_at") or item.get("ts") or "n/a"
            signal = item.get("signal") or "n/a"
            score = item.get("score")
            score_text = str(score) if score is not None else "n/a"
            url = item.get("url") or "n/a"
            news_lines.append(
                f"{idx}. [{source}] {headline} | published_at={published_at} | signal={signal} | score={score_text} | url={url}"
            )

        if news_lines:
            news_block = "\n".join(news_lines)
        else:
            news_block = "No recent news available."

        base_prompt = f"""Analyze {context.symbol} stock for a {context.horizon.value} horizon.

Symbol: {context.symbol}
Analysis Date: {context.as_of}
Horizon: {context.horizon.value}
Bars Summary: {context.bars_summary}
Indicators: {context.indicators}
Fundamentals: {context.fundamentals}
Sentiment Context: {context.sentiment_context}

News (latest up to 5 items):
{news_block}

"""
        
        if phase1_outputs:
            base_prompt += "\n## Phase 1 Analyst Outputs:\n"
            for name, data in phase1_outputs.items():
                if data.get("output"):
                    base_prompt += f"\n### {name}:\n{data['output']}\n"
        
        if phase2_outputs:
            base_prompt += "\n## Phase 2 Debate Outputs:\n"
            for name, data in phase2_outputs.items():
                if data.get("output"):
                    base_prompt += f"\n### {name}:\n{data['output']}\n"
        
        base_prompt += f"""

Provide your analysis as a valid JSON object following the schema. 
Respond ONLY with the JSON object, no additional text.
Schema version: {SCHEMA_VERSION}
"""
        
        return base_prompt


def create_orchestrator(
    database_url: str,
    use_stub: bool = True,
    use_multi_provider: bool = False,
    provider_mapping: str | None = None,
) -> ResearchOrchestrator:
    """Factory function to create orchestrator.
    
    Args:
        database_url: Database connection string
        use_stub: If True, use stub client for testing
        use_multi_provider: If True, use multiple AI providers for diverse perspectives
        provider_mapping: Custom provider mapping (e.g., "bull=anthropic,bear=openai")
    
    Returns:
        ResearchOrchestrator instance
    """
    from quantdog.research.llm_client import create_llm_client
    
    if use_stub:
        llm_client = create_llm_client("stub")
        settings = get_settings()
    else:
        settings = get_settings()
        if not settings.enable_ai_analysis:
            llm_client = create_llm_client("noop")
        elif use_multi_provider:
            # Use multiple providers for research
            llm_client = create_llm_client("multi", provider_mapping=provider_mapping)
        else:
            # Use single provider (default: OpenAI)
            llm_client = create_llm_client("real", provider="openai")
    
    news_resolution = resolve_news_provider(settings)

    return ResearchOrchestrator(
        database_url=database_url,
        llm_client=llm_client,
        news_provider=news_resolution.provider,
    )
