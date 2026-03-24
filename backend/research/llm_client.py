# LLM Client Interface and Implementations

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from research.models import (
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
    
    # Provider configurations
    PROVIDERS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "env_key": "OPENAI_API_KEY",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "default_model": "claude-3-haiku-20240307",
            "env_key": "ANTHROPIC_API_KEY",
            "requires_extra_headers": True,
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-1.5-flash",
            "env_key": "GOOGLE_API_KEY",
        },
        "glm": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4-flash",
            "env_key": "ZHIPU_API_KEY",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "default_model": "anthropic/claude-3-haiku",
            "env_key": "OPENROUTER_API_KEY",
        },
    }
    
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        provider: str = "openai",
    ):
        import os
        
        # Determine provider and get appropriate config
        if provider not in self.PROVIDERS:
            provider = "openai"
        
        config = self.PROVIDERS[provider]
        
        self._provider = provider
        self._api_key = api_key or os.getenv(config["env_key"])
        self._base_url = base_url or os.getenv(f"{provider.upper()}_BASE_URL") or config["base_url"]
        self._default_model = os.getenv(f"{provider.upper()}_MODEL") or default_model or config["default_model"]
        self._requires_extra_headers = config.get("requires_extra_headers", False)
        
        # Provider-specific headers
        self._extra_headers = {}
        if provider == "anthropic" and self._api_key:
            self._extra_headers["x-api-key"] = self._api_key
            self._extra_headers["anthropic-version"] = "2023-06-01"
    
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
            "Content-Type": "application/json",
        }
        
        # Add provider-specific headers
        headers.update(self._extra_headers)
        
        if self._provider == "anthropic":
            # Anthropic uses a different format
            messages = [
                {"role": "user", "content": system_prompt + "\n\n" + user_prompt}
            ]
            payload = {
                "model": self._default_model,
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,
            }
        elif self._provider == "google":
            # Google Gemini format
            messages = {
                "contents": [{
                    "parts": [{"text": system_prompt + "\n\n" + user_prompt}]
                }]
            }
            payload = {
                "contents": messages["contents"],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2000,
                },
            }
            # No Authorization header for Google - key goes in URL
            # Add response format for Gemini
            if response_schema:
                payload["generationConfig"]["responseMimeType"] = "application/json"
                payload["schema"] = response_schema.model_json_schema()
        else:
            # OpenAI / GLM / OpenRouter format
            headers["Authorization"] = f"Bearer {self._api_key}"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            payload = {
                "model": self._default_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            }
            
            # Add response format for JSON output
            if response_schema and self._provider in ("openai", "openrouter"):
                import json
                json_schema = response_schema.model_json_schema()
                
                # Function to resolve $ref and convert to simple type
                def resolve_refs(schema, defs=None):
                    if defs is None:
                        defs = schema.get("$defs", {})
                    
                    if isinstance(schema, str):
                        # Handle $ref
                        if schema.startswith("#/$defs/"):
                            ref_name = schema.replace("#/$defs/", "")
                            if ref_name in defs:
                                return {"type": "string", "enum": defs[ref_name].get("enum", [])}
                    elif isinstance(schema, dict):
                        resolved = {}
                        for key, value in schema.items():
                            # Skip keys not supported by OpenAI
                            if key in ["description", "title", "examples"]:
                                continue
                            
                            if key == "$ref":
                                # Replace $ref with resolved type
                                ref_name = value.replace("#/$defs/", "")
                                if ref_name in defs:
                                    resolved["type"] = "string"
                                    if "enum" in defs[ref_name]:
                                        resolved["enum"] = defs[ref_name]["enum"]
                            elif key == "default":
                                continue  # Skip defaults
                            elif key in ["type", "properties", "items", "enum", "required", "additionalProperties"]:
                                resolved[key] = resolve_refs(value, defs)
                            else:
                                # Try to resolve anyway
                                try:
                                    resolved[key] = resolve_refs(value, defs)
                                except:
                                    pass
                        return resolved
                    elif isinstance(schema, list):
                        return [resolve_refs(item, defs) for item in schema]
                    else:
                        return schema
                    
                    return schema
                
                # Clean and resolve schema for OpenAI
                clean_schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                    "required": []
                }
                
                model_fields = response_schema.model_fields
                defs = json_schema.get("$defs", {})
                
                for field_name, field_info in model_fields.items():
                    if field_info.is_required():
                        field_schema = json_schema["properties"].get(field_name)
                        if field_schema:
                            resolved = resolve_refs(field_schema, defs)
                            if resolved:
                                clean_schema["properties"][field_name] = resolved
                                clean_schema["required"].append(field_name)
                
                if not clean_schema["required"]:
                    clean_schema.pop("required")
                
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "schema": clean_schema,
                        "strict": True,
                    }
                }
        
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                # Build the request URL
                if self._provider == "google":
                    url = f"{self._base_url}/models/{self._default_model}:generateContent?key={self._api_key}"
                else:
                    url = f"{self._base_url}/chat/completions"
                
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                    follow_redirects=True,
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Parse response based on provider
                if self._provider == "google":
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Handle markdown code blocks from Gemini
                    # Example: ```json\n{"test": "gemini"}\n```
                    content = content.strip()
                    if content.startswith("```"):
                        # Remove markdown code block markers
                        content = content[3:].strip()
                        if content.startswith(("json", "JSON")):
                            content = content[4:].strip()
                        # Remove closing ```
                        if content.endswith("```"):
                            content = content[:-3].strip()
                else:
                    content = data["choices"][0]["message"]["content"]
                
                # Parse JSON response
                output = json.loads(content)
                
                # Validate against schema
                if response_schema:
                    validated = response_schema.model_validate(output)
                    output = validated.model_dump()
                
                model_id = data.get("model", self._default_model)
                return output, AgentStatus.OK, model_id
                
        except httpx.TimeoutException as e:
            print(f"Timeout in {self._provider}: {e}")
            return {}, AgentStatus.TIMEOUT, self._default_model
        except httpx.HTTPStatusError as e:
            error_text = e.response.text[:500] if hasattr(e, 'response') else str(e)
            print(f"HTTP error in {self._provider}: {e.response.status_code} - {error_text}")
            return {}, AgentStatus.ERROR, self._default_model
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError in {self._provider}: {e}")
            return {}, AgentStatus.INVALID_OUTPUT, self._default_model
        except Exception as e:
            print(f"Exception in {self._provider}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {}, AgentStatus.ERROR, self._default_model


class MultiProviderLLMClient(LLMClient):
    """Multi-provider LLM client that routes to different providers.
    
    This client can use different AI providers for different agents,
    enabling diverse perspectives in debates.
    """
    
    # Default agent -> provider mapping for debate
    # 配置：仅使用 OpenAI (GPT) 和 Google (Gemini) 两个provider
    DEFAULT_MAPPING = {
        # Phase 1 agents (OpenAI + Google 平衡分配)
        "market_analyst": "openai",
        "fundamental_analyst": "openai",
        "news_analyst": "google",
        "sentiment_analyst": "google",
        "risk_analyst": "openai",
        # Phase 2 debate agents (对抗性配置：Bull用OpenAI，Bear用Google)
        "bull_researcher": "openai",
        "bear_researcher": "google",
        # Phase 3 decision (综合OpenAI能力做最终决策)
        "trader_agent": "openai",
    }
    
    def __init__(
        self,
        provider_mapping: dict[str, str] | None = None,
    ):
        import os
        
        # Get environment-configured API keys for each provider
        self._providers: dict[str, RealLLMClient] = {}
        
        mapping = provider_mapping or self.DEFAULT_MAPPING
        
        # Initialize clients for each provider needed
        needed_providers = set(mapping.values())
        for provider in needed_providers:
            if provider in RealLLMClient.PROVIDERS:
                self._providers[provider] = RealLLMClient(provider=provider)
        
        self._mapping = mapping
    
    def is_available(self) -> bool:
        """Check if at least one provider is available."""
        return any(p.is_available() for p in self._providers.values())
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type | None = None,
        timeout_seconds: float = 30.0,
        agent_name: str | None = None,
    ) -> tuple[dict[str, Any], AgentStatus, str | None]:
        """Call LLM using provider based on agent name."""
        
        # Determine which provider to use
        provider_name = "openai"  # default
        if agent_name and agent_name in self._mapping:
            provider_name = self._mapping[agent_name]
        
        # Get the client
        client = self._providers.get(provider_name)
        
        if client is None or not client.is_available():
            # Fallback to any available provider
            for fallback_client in self._providers.values():
                if fallback_client.is_available():
                    client = fallback_client
                    break
        
        if client is None:
            return {}, AgentStatus.ERROR, None
        
        return client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
            timeout_seconds=timeout_seconds,
        )


def create_llm_client(
    client_type: str = "stub",
    **kwargs,
) -> LLMClient:
    """Factory function to create LLM client.
    
    Args:
        client_type: One of "stub", "noop", "real", "multi"
        - "stub": Returns deterministic test data
        - "noop": Forces baseline mode (no AI)
        - "real": Single provider (uses OPENAI_API_KEY by default)
        - "multi": Multiple providers (OpenAI, Claude, Gemini, GLM)
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
            provider=kwargs.get("provider", "openai"),
        )
    elif client_type == "multi":
        # Parse custom provider mapping from kwargs
        provider_mapping = kwargs.get("provider_mapping")
        if provider_mapping and isinstance(provider_mapping, str):
            # Convert string like "bull=anthropic,bear=openai" to dict
            provider_mapping = {}
            for pair in kwargs.get("provider_mapping", "").split(","):
                if "=" in pair:
                    agent, provider = pair.split("=", 1)
                    provider_mapping[agent.strip()] = provider.strip()
        return MultiProviderLLMClient(provider_mapping=provider_mapping)
    else:
        raise ValueError(f"Unknown client type: {client_type}")
