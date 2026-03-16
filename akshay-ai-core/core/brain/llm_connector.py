"""
============================================================
AKSHAY AI CORE — LLM Connector
============================================================
Multi-provider LLM abstraction layer supporting:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (Local models)
============================================================
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from core.config import settings
from core.utils.logger import get_logger, audit_logger

logger = get_logger("brain.llm")


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LOCAL = "local"


@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LLMResponse:
    """LLM response container."""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: Optional[str] = None
    latency_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.kwargs = kwargs
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate a completion."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider (GPT-4, GPT-3.5)."""
    
    async def complete(
        self,
        messages: List[Message],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using OpenAI."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key or settings.OPENAI_API_KEY)
            
            formatted_messages = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            
            start = datetime.utcnow()
            response = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                provider="openai",
                tokens_used=response.usage.total_tokens,
                tokens_prompt=response.usage.prompt_tokens,
                tokens_completion=response.usage.completion_tokens,
                finish_reason=response.choices[0].finish_reason,
                latency_ms=latency,
            )
            
        except Exception as e:
            logger.error("OpenAI completion failed", error=str(e))
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream completion using OpenAI."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key or settings.OPENAI_API_KEY)
            
            formatted_messages = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            
            stream = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error("OpenAI stream failed", error=str(e))
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI."""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key or settings.OPENAI_API_KEY)
            
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("OpenAI embedding failed", error=str(e))
            raise


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider (Claude)."""
    
    async def complete(
        self,
        messages: List[Message],
        model: str = "claude-3-5-sonnet-latest",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Anthropic."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.api_key or settings.ANTHROPIC_API_KEY)
            
            # Extract system message
            system = ""
            formatted_messages = []
            
            for m in messages:
                if m.role == "system":
                    system = m.content
                else:
                    formatted_messages.append({
                        "role": m.role,
                        "content": m.content,
                    })
            
            start = datetime.utcnow()
            response = await client.messages.create(
                model=model,
                system=system,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return LLMResponse(
                content=response.content[0].text,
                model=model,
                provider="anthropic",
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                tokens_prompt=response.usage.input_tokens,
                tokens_completion=response.usage.output_tokens,
                finish_reason=response.stop_reason,
                latency_ms=latency,
            )
            
        except Exception as e:
            logger.error("Anthropic completion failed", error=str(e))
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: str = "claude-3-5-sonnet-latest",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream completion using Anthropic."""
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.api_key or settings.ANTHROPIC_API_KEY)
            
            system = ""
            formatted_messages = []
            
            for m in messages:
                if m.role == "system":
                    system = m.content
                else:
                    formatted_messages.append({
                        "role": m.role,
                        "content": m.content,
                    })
            
            async with client.messages.stream(
                model=model,
                system=system,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            logger.error("Anthropic stream failed", error=str(e))
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Anthropic doesn't have embeddings - use OpenAI fallback."""
        provider = OpenAIProvider()
        return await provider.embed(text)


class GoogleProvider(BaseLLMProvider):
    """Google provider (Gemini)."""
    
    async def complete(
        self,
        messages: List[Message],
        model: str = "gemini-pro",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Google Gemini."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key or settings.GOOGLE_API_KEY)
            
            model_instance = genai.GenerativeModel(model)
            
            # Convert messages to Gemini format
            chat = model_instance.start_chat(history=[])
            
            start = datetime.utcnow()
            
            # Process messages
            for m in messages:
                if m.role == "user":
                    response = await asyncio.to_thread(
                        chat.send_message,
                        m.content,
                        generation_config={
                            "temperature": temperature,
                            "max_output_tokens": max_tokens,
                        },
                    )
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return LLMResponse(
                content=response.text,
                model=model,
                provider="google",
                latency_ms=latency,
            )
            
        except Exception as e:
            logger.error("Google completion failed", error=str(e))
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: str = "gemini-pro",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream completion using Google Gemini."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key or settings.GOOGLE_API_KEY)
            
            model_instance = genai.GenerativeModel(model)
            
            # Get last user message
            user_content = ""
            for m in reversed(messages):
                if m.role == "user":
                    user_content = m.content
                    break
            
            response = await asyncio.to_thread(
                model_instance.generate_content,
                user_content,
                stream=True,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error("Google stream failed", error=str(e))
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Google."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key or settings.GOOGLE_API_KEY)
            
            result = await asyncio.to_thread(
                genai.embed_content,
                model="models/embedding-001",
                content=text,
            )
            
            return result["embedding"]
            
        except Exception as e:
            logger.error("Google embedding failed", error=str(e))
            raise


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local models."""
    
    def __init__(self, base_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url or settings.OLLAMA_HOST
    
    async def complete(
        self,
        messages: List[Message],
        model: str = "llama3",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Ollama."""
        try:
            import httpx
            
            formatted_messages = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            
            start = datetime.utcnow()
            
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": formatted_messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return LLMResponse(
                content=data["message"]["content"],
                model=model,
                provider="ollama",
                latency_ms=latency,
                tokens_used=data.get("eval_count", 0),
            )
            
        except Exception as e:
            logger.error("Ollama completion failed", error=str(e))
            raise
    
    async def stream(
        self,
        messages: List[Message],
        model: str = "llama3",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream completion using Ollama."""
        try:
            import httpx
            
            formatted_messages = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": formatted_messages,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                ) as response:
                    import json
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if "message" in data:
                                yield data["message"].get("content", "")
                    
        except Exception as e:
            logger.error("Ollama stream failed", error=str(e))
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Ollama."""
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            return data["embedding"]
            
        except Exception as e:
            logger.error("Ollama embedding failed", error=str(e))
            raise


class LLMConnector:
    """
    Multi-provider LLM connector.
    
    Features:
    - Multiple provider support
    - Automatic fallback
    - Response caching
    - Usage tracking
    - Cost estimation
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._default_provider: Optional[str] = None
        self._usage: Dict[str, Dict] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize configured providers."""
        # OpenAI
        if settings.OPENAI_API_KEY:
            self._providers["openai"] = OpenAIProvider()
            if not self._default_provider:
                self._default_provider = "openai"
        
        # Anthropic
        if settings.ANTHROPIC_API_KEY:
            self._providers["anthropic"] = AnthropicProvider()
            if not self._default_provider:
                self._default_provider = "anthropic"
        
        # Google
        if settings.GOOGLE_API_KEY:
            self._providers["google"] = GoogleProvider()
            if not self._default_provider:
                self._default_provider = "google"
        
        # Ollama (always available for local)
        self._providers["ollama"] = OllamaProvider()
        if not self._default_provider:
            self._default_provider = "ollama"
        
        logger.info(
            "LLM providers initialized",
            providers=list(self._providers.keys()),
            default=self._default_provider,
        )
    
    def get_provider(self, name: Optional[str] = None) -> BaseLLMProvider:
        """Get a provider by name."""
        provider_name = name or self._default_provider
        
        if provider_name not in self._providers:
            raise ValueError(f"Provider not configured: {provider_name}")
        
        return self._providers[provider_name]
    
    async def complete(
        self,
        messages: List[Union[Message, Dict]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        fallback: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a completion.
        
        Args:
            messages: List of messages
            provider: Provider to use
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            fallback: Whether to try other providers on failure
            
        Returns:
            LLMResponse with the completion
        """
        # Convert dicts to Message objects
        normalized_messages = []
        for m in messages:
            if isinstance(m, dict):
                normalized_messages.append(Message(**m))
            else:
                normalized_messages.append(m)
        
        provider_name = provider or self._default_provider
        
        # Get model for provider
        if not model:
            model = self._get_default_model(provider_name)
        
        providers_to_try = [provider_name]
        if fallback:
            providers_to_try.extend([
                p for p in self._providers.keys()
                if p != provider_name
            ])
        
        last_error = None
        
        for p_name in providers_to_try:
            try:
                p = self._providers.get(p_name)
                if not p:
                    continue
                
                response = await p.complete(
                    messages=normalized_messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                
                # Track usage
                self._track_usage(p_name, response)
                
                audit_logger.log(
                    action="llm_completion",
                    details={
                        "provider": p_name,
                        "model": model,
                        "tokens": response.tokens_used,
                        "latency_ms": response.latency_ms,
                    },
                )
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {p_name} failed", error=str(e))
                
                if fallback:
                    continue
                raise
        
        raise RuntimeError(f"All providers failed. Last error: {last_error}")
    
    async def stream(
        self,
        messages: List[Union[Message, Dict]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        # Convert dicts to Message objects
        normalized_messages = []
        for m in messages:
            if isinstance(m, dict):
                normalized_messages.append(Message(**m))
            else:
                normalized_messages.append(m)
        
        provider_name = provider or self._default_provider
        
        if not model:
            model = self._get_default_model(provider_name)
        
        p = self.get_provider(provider_name)
        
        async for chunk in p.stream(
            messages=normalized_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk
    
    async def embed(
        self,
        text: str,
        provider: Optional[str] = None,
    ) -> List[float]:
        """Generate embeddings."""
        provider_name = provider or self._default_provider
        p = self.get_provider(provider_name)
        return await p.embed(text)
    
    def _get_default_model(self, provider: str) -> str:
        """Get default model for a provider."""
        defaults = {
            "openai": "gpt-4",
            "anthropic": "claude-3-5-sonnet-latest",
            "google": "gemini-pro",
            "ollama": settings.AI_MODEL,
        }
        return defaults.get(provider, "gpt-4")
    
    def _track_usage(self, provider: str, response: LLMResponse) -> None:
        """Track usage statistics."""
        if provider not in self._usage:
            self._usage[provider] = {
                "requests": 0,
                "tokens_prompt": 0,
                "tokens_completion": 0,
                "latency_sum": 0,
            }
        
        self._usage[provider]["requests"] += 1
        self._usage[provider]["tokens_prompt"] += response.tokens_prompt
        self._usage[provider]["tokens_completion"] += response.tokens_completion
        self._usage[provider]["latency_sum"] += response.latency_ms
    
    def get_usage(self) -> Dict[str, Dict]:
        """Get usage statistics."""
        return self._usage.copy()
    
    @property
    def available_providers(self) -> List[str]:
        """Get list of available providers."""
        return list(self._providers.keys())


# Global LLM connector instance
llm = LLMConnector()
