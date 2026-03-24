# Research module - Agent output schemas

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


SCHEMA_VERSION = "1.0.0"


class Decision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SignalStrength(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    SLIGHTLY_BEARISH = "slightly_bearish"
    NEUTRAL = "neutral"
    SLIGHTLY_BULLISH = "slightly_bullish"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class AgentStatus(str, Enum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SKIPPED = "SKIPPED"


# =============================================================================
# Phase 1: Analyst Agents
# =============================================================================


class MarketAnalystOutput(BaseModel):
    """Market analyst output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    signal: SignalStrength = Field(description="Overall market signal")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    key_levels: dict[str, float] = Field(
        default_factory=dict,
        description="Key support/resistance levels",
        examples=[{"support": 150.0, "resistance": 180.0}]
    )
    trend_summary: str = Field(
        max_length=500,
        description="Brief trend analysis"
    )
    catalysts: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="List of market catalysts"
    )
    risk_factors: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Identified risk factors"
    )
    
    @field_validator("signal", "confidence", mode="before")
    @classmethod
    def validate_enum(cls, v):
        if isinstance(v, str):
            return v
        return v


class FundamentalAnalystOutput(BaseModel):
    """Fundamental analyst output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    valuation_signal: SignalStrength = Field(description="Valuation signal")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    pe_ratio: float | None = Field(default=None, description="P/E ratio")
    earnings_growth: float | None = Field(
        default=None,
        description="Expected earnings growth percentage"
    )
    revenue_trend: str = Field(
        max_length=100,
        description="Revenue trend summary"
    )
    key_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Key fundamental metrics"
    )
    competitors_comparison: str = Field(
        max_length=500,
        description="Brief competitor analysis"
    )
    risks: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Fundamental risks"
    )


class NewsAnalystOutput(BaseModel):
    """News analyst output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    sentiment: SignalStrength = Field(description="News sentiment")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    headline_summary: str = Field(
        max_length=500,
        description="Summary of recent news"
    )
    key_stories: list[dict[str, str]] = Field(
        max_length=20,
        default_factory=list,
        description="Key news stories with sentiment",
        examples=[{"title": "Company beats earnings", "sentiment": "bullish"}]
    )
    impact_assessment: str = Field(
        max_length=300,
        description="Assessment of news impact"
    )


class SentimentAnalystOutput(BaseModel):
    """Sentiment analyst output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    overall_sentiment: SignalStrength = Field(description="Overall sentiment")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    social_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Social media metrics"
    )
    market_sentiment_context: str = Field(
        max_length=300,
        description="Market sentiment context (VIX, SPY, etc.)"
    )
    investor_mood: str = Field(
        max_length=100,
        description="Current investor mood"
    )
    market_sentiment_context: str = Field(
        max_length=300,
        description="Market sentiment context (VIX, SPY, etc.)"
    )
    investor_mood: str = Field(
        max_length=100,
        description="Current investor mood"
    )


class RiskAnalystOutput(BaseModel):
    """Risk analyst output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    risk_level: ConfidenceLevel = Field(description="Overall risk level")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    volatility_estimate: float | None = Field(
        default=None,
        description="Estimated volatility"
    )
    risk_factors: list[str] = Field(
        max_length=15,
        default_factory=list,
        description="Identified risk factors"
    )
    risk_score: int = Field(
        ge=0,
        le=100,
        description="Overall risk score 0-100"
    )
    mitigation_notes: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Risk mitigation notes"
    )


# Workaround for missing pydantic field
from pydantic import __version__ as _pydantic_version

class DescriptionField:
    """Compatibility field for older pydantic versions."""
    pass

# Use regular Field for confidence in SentimentAnalystOutput
SentimentAnalystOutput.model_fields["confidence"] = Field(
    description="Confidence level",
    validation_alias="confidence"
)


# =============================================================================
# Phase 2: Debate Agents
# =============================================================================


class BullResearcherOutput(BaseModel):
    """Bull researcher (bullish debate) output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    thesis: str = Field(
        max_length=1000,
        description="Bullish thesis"
    )
    key_arguments: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Supporting arguments"
    )
    price_target: float | None = Field(
        default=None,
        description="Bullish price target"
    )
    timeframe: str = Field(
        max_length=50,
        description="Expected timeframe for thesis"
    )
    confidence: ConfidenceLevel = Field(description="Confidence level")
    counterarguments_addressed: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Bearish arguments addressed"
    )


class BearResearcherOutput(BaseModel):
    """Bear researcher (bearish debate) output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    thesis: str = Field(
        max_length=1000,
        description="Bearish thesis"
    )
    key_arguments: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Supporting arguments"
    )
    price_target: float | None = Field(
        default=None,
        description="Bearish price target"
    )
    timeframe: str = Field(
        max_length=50,
        description="Expected timeframe for thesis"
    )
    confidence: ConfidenceLevel = Field(description="Confidence level")
    counterarguments_addressed: list[str] = Field(
        max_length=10,
        default_factory=list,
        description="Bullish arguments addressed"
    )


# =============================================================================
# Phase 3: Trader Decision
# =============================================================================


class TraderAgentOutput(BaseModel):
    """Trader agent final decision output schema."""
    
    model_config = {"extra": "forbid"}
    
    schema_version: str = Field(default=SCHEMA_VERSION)
    decision: Decision = Field(description="Final trading decision")
    confidence: int = Field(
        ge=0,
        le=100,
        description="Confidence percentage"
    )
    reasoning: str = Field(
        max_length=2000,
        description="Detailed reasoning"
    )
    key_factors: list[str] = Field(
        max_length=15,
        default_factory=list,
        description="Key decision factors"
    )
    risk_assessment: str = Field(
        max_length=500,
        description="Risk assessment"
    )
    position_sizing_note: str | None = Field(
        default=None,
        max_length=200,
        description="Position sizing recommendation"
    )


# =============================================================================
# Agent Output Container
# =============================================================================


class AgentOutput(BaseModel):
    """Container for any agent output with metadata."""
    
    model_config = {"extra": "forbid"}
    
    phase: int = Field(ge=1, le=3, description="Phase number (1, 2, or 3)")
    agent_name: str = Field(
        description="Agent name (e.g., 'market_analyst', 'bull_researcher')"
    )
    status: AgentStatus = Field(description="Execution status")
    output: dict[str, Any] = Field(
        description="Validated output data as dict"
    )
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Validation errors if any"
    )
    duration_ms: int | None = Field(
        default=None,
        description="Execution duration in milliseconds"
    )
    model_id: str | None = Field(
        default=None,
        description="LLM model used (if applicable)"
    )


# =============================================================================
# Run Context
# =============================================================================


class Horizon(str, Enum):
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"
    ONE_YEAR = "1y"


class RunContext(BaseModel):
    """Shared context passed to all agents."""
    
    model_config = {"extra": "forbid"}
    
    symbol: str = Field(description="Stock symbol")
    as_of: str = Field(description="Analysis date (YYYY-MM-DD)")
    horizon: Horizon = Field(description="Analysis horizon")
    language: str = Field(default="en", description="Response language")
    
    # Data sources (populated by orchestrator)
    bars_summary: dict[str, Any] | None = Field(
        default=None,
        description="Bars data summary"
    )
    indicators: dict[str, Any] | None = Field(
        default=None,
        description="Technical indicators"
    )
    fundamentals: dict[str, Any] | None = Field(
        default=None,
        description="Fundamental data"
    )
    news: list[dict[str, Any]] = Field(
        default_factory=list,
        description="News items"
    )
    sentiment_context: dict[str, Any] | None = Field(
        default=None,
        description="Market sentiment context"
    )


# =============================================================================
# Research Run
# =============================================================================


class ResearchRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class ResearchRun(BaseModel):
    """Research run result schema."""
    
    model_config = {"extra": "forbid"}
    
    run_id: str = Field(description="Unique run identifier")
    symbol: str = Field(description="Stock symbol")
    requested_at: str = Field(description="Request timestamp")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    status: ResearchRunStatus = Field(description="Run status")
    final_decision: Decision | None = Field(default=None, description="Final decision")
    final_confidence: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Final confidence"
    )
    baseline_used: bool = Field(
        default=False,
        description="Whether baseline fallback was used"
    )
    quality_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Quality score (ok_agents / 8 * 100)"
    )
    error_summary: str | None = Field(
        default=None,
        max_length=1000,
        description="Error summary if any"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Run configuration"
    )
