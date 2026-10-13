import logging

import httpx

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.anthropic")


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic provider interfacing directly with Claude's Messages API over HTTP.
    """

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        url = self.api_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model or "claude-3-5-sonnet-20240620",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return str(result["content"][0]["text"])
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            raise RuntimeError(f"Anthropic provider call failed: {e}") from e

