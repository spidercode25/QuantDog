# Research module exports

from quantdog.research.models import (
    SCHEMA_VERSION,
    Decision,
    ConfidenceLevel,
    SignalStrength,
    AgentStatus,
    # Phase 1
    MarketAnalystOutput,
    FundamentalAnalystOutput,
    NewsAnalystOutput,
    SentimentAnalystOutput,
    RiskAnalystOutput,
    # Phase 2
    BullResearcherOutput,
    BearResearcherOutput,
    # Phase 3
    TraderAgentOutput,
    # Container
    AgentOutput,
    # Context
    RunContext,
    Horizon,
    # Run
    ResearchRunStatus,
    ResearchRun,
)

from quantdog.research.llm_client import (
    LLMClient,
    StubLLMClient,
    NoopLLMClient,
    RealLLMClient,
    create_llm_client,
)

from quantdog.research.repository import (
    create_research_run,
    get_research_run,
    update_research_run_status,
    save_agent_output,
    get_agent_outputs,
)

from quantdog.research.orchestrator import (
    ResearchOrchestrator,
    create_orchestrator,
)

__all__ = [
    # Models
    "SCHEMA_VERSION",
    "Decision",
    "ConfidenceLevel",
    "SignalStrength",
    "AgentStatus",
    "MarketAnalystOutput",
    "FundamentalAnalystOutput",
    "NewsAnalystOutput",
    "SentimentAnalystOutput",
    "RiskAnalystOutput",
    "BullResearcherOutput",
    "BearResearcherOutput",
    "TraderAgentOutput",
    "AgentOutput",
    "RunContext",
    "Horizon",
    "ResearchRunStatus",
    "ResearchRun",
    # Clients
    "LLMClient",
    "StubLLMClient",
    "NoopLLMClient",
    "RealLLMClient",
    "create_llm_client",
    # Repository
    "create_research_run",
    "get_research_run",
    "update_research_run_status",
    "save_agent_output",
    "get_agent_outputs",
    # Orchestrator
    "ResearchOrchestrator",
    "create_orchestrator",
]
