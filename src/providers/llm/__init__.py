from src.config import LLMConfig
from src.providers.llm.anthropic import AnthropicProvider
from src.providers.llm.base import BaseLLMProvider
from src.providers.llm.gemini import GeminiProvider
from src.providers.llm.local_agy import LocalAGYProvider
from src.providers.llm.openai import OpenAIProvider
from src.providers.llm.agy_cli import AGYCLIProvider


def get_llm_provider(config: LLMConfig) -> BaseLLMProvider:
    """
    Factory function to retrieve the configured LLM provider.
    """
    provider_name = config.provider.lower()

    if provider_name == "local_agy":
        return LocalAGYProvider(
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif provider_name == "agy_cli":
        return AGYCLIProvider(
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif provider_name == "openai":
        return OpenAIProvider(
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url or None,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url or None,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    elif provider_name == "gemini":
        return GeminiProvider(
            api_key=config.api_key,
            model=config.model,
            api_url=config.api_url or None,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")


__all__ = [
    "BaseLLMProvider",
    "LocalAGYProvider",
    "AGYCLIProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_llm_provider",
]
