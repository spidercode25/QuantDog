# LLM Client Interface and Implementations

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from quantdog.research.models import (
    RunContext,
    AgentStatus,
    AgentOutput,
    SCHEMA_VERSION,
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
)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Execute LLM completion.
        
        Args:
            system_prompt: System instruction
            user_prompt: User prompt
            response_schema: Pydantic model to validate against
            timeout_seconds: Request timeout
            
        Returns:
            Tuple of (validated_output_dict, status, model_id or None)
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if client is available for requests."""
        pass


class StubLLMClient(LLMClient):
    """Deterministic stub client for testing and CI."""
    
    def __init__(self, deterministic_output: dict[str, Any] | None = None):
        self._default_output = deterministic_output
    
    def is_available(self) -> bool:
        return True
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Return deterministic stub output."""
        
        output = self._default_output or self._generate_stub_output(response_schema)
        
        # Try to validate with schema if provided
        validation_errors: list[str] = []
        if response_schema:
            try:
                response_schema.model_validate(output)
            except Exception as e:
                validation_errors.append(str(e))
                return output, AgentStatus.INVALID_OUTPUT, "stub"
        
        return output, AgentStatus.OK, "stub"
    
    def _generate_stub_output(
        self,
        schema_type: type | None,
    ) -> dict[str, Any]:
        """Generate appropriate stub output based on expected schema."""
        
        if schema_type == MarketAnalystOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "signal": "neutral",
                "confidence": "medium",
                "key_levels": {"support": 150.0, "resistance": 180.0},
                "trend_summary": "Stub: Stock shows neutral momentum",
                "catalysts": ["Stub catalyst"],
                "risk_factors": []
            }
        elif schema_type == FundamentalAnalystOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "valuation_signal": "neutral",
                "confidence": "medium",
                "pe_ratio": 25.0,
                "earnings_growth": 10.0,
                "revenue_trend": "stable",
                "key_metrics": {"roe": 0.15},
                "competitors_comparison": "In line with sector",
                "risks": []
            }
        elif schema_type == NewsAnalystOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "sentiment": "neutral",
                "confidence": "medium",
                "headline_summary": "Stub: No significant news",
                "key_stories": [],
                "impact_assessment": "Neutral impact expected"
            }
        elif schema_type == SentimentAnalystOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "overall_sentiment": "neutral",
                "confidence": "medium",
                "social_metrics": {},
                "market_sentiment_context": "VIX near average",
                "investor_mood": "cautious"
            }
        elif schema_type == RiskAnalystOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "risk_level": "medium",
                "confidence": "medium",
                "volatility_estimate": 0.20,
                "risk_factors": [],
                "risk_score": 50,
                "mitigation_notes": []
            }
        elif schema_type == BullResearcherOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "thesis": "Stub: Bullish thesis - strong fundamentals",
                "key_arguments": ["Solid earnings", "Good momentum"],
                "price_target": 200.0,
                "timeframe": "6 months",
                "confidence": "medium",
                "counterarguments_addressed": ["Bear case addressed"]
            }
        elif schema_type == BearResearcherOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "thesis": "Stub: Bearish thesis - overvalued",
                "key_arguments": ["High P/E", "Weak growth"],
                "price_target": 120.0,
                "timeframe": "6 months",
                "confidence": "medium",
                "counterarguments_addressed": ["Bull case addressed"]
            }
        elif schema_type == TraderAgentOutput:
            return {
                "schema_version": SCHEMA_VERSION,
                "decision": "HOLD",
                "confidence": 50,
                "reasoning": "Stub: Balanced analysis, no clear signal",
                "key_factors": ["Neutral indicators"],
                "risk_assessment": "Medium risk",
                "position_sizing_note": "Small position recommended"
            }
        
        # Default fallback
        return {"schema_version": SCHEMA_VERSION, "note": "stub output"}


class NoopLLMClient(LLMClient):
    """No-op client that forces baseline-only mode."""
    
    def is_available(self) -> bool:
        return True
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Always return error status to force baseline."""
        return {}, AgentStatus.SKIPPED, "noop"


class RealLLMClient(LLMClient):
    """Real LLM client that calls external API."""
    
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
    ):
        import os
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._default_model = default_model
    
    def is_available(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Call external LLM API."""
        import httpx
        
        if not self.is_available():
            return {}, AgentStatus.ERROR, None
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        # Build request payload
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        payload: dict[str, Any] = {
            "model": self._default_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        
        # Add response format for JSON output if schema provided
        if response_schema:
            # Extract JSON schema from pydantic model
            json_schema = response_schema.model_json_schema()
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": json_schema,
                    "strict": True,
                }
            }
        
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Parse JSON response
                output = json.loads(content)
                
                # Validate against schema
                if response_schema:
                    validated = response_schema.model_validate(output)
                    output = validated.model_dump()
                
                model_id = data.get("model", self._default_model)
                return output, AgentStatus.OK, model_id
                
        except httpx.TimeoutException:
            return {}, AgentStatus.TIMEOUT, self._default_model
        except httpx.HTTPStatusError as e:
            return {}, AgentStatus.ERROR, self._default_model
        except json.JSONDecodeError:
            return {}, AgentStatus.INVALID_OUTPUT, self._default_model
        except Exception:
            return {}, AgentStatus.ERROR, self._default_model


def create_llm_client(
    client_type: str = "stub",
    **kwargs,
) -> LLMClient:
    """Factory function to create LLM client.
    
    Args:
        client_type: One of "stub", "noop", "real"
        **kwargs: Additional arguments passed to client constructor
    
    Returns:
        LLMClient instance
    """
    if client_type == "stub":
        return StubLLMClient(kwargs.get("deterministic_output"))
    elif client_type == "noop":
        return NoopLLMClient()
    elif client_type == "real":
        return RealLLMClient(
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            default_model=kwargs.get("default_model", "gpt-4o-mini"),
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")
