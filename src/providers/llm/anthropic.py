import logging
import re

import httpx
from pydantic import BaseModel

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.anthropic")


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic provider interfacing directly with Claude's Messages API over HTTP.
    """

    def _clean_json_response(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()

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

    def generate_json(self, prompt: str, schema: type[BaseModel], system_prompt: str | None = None) -> BaseModel:
        json_instruction = (
            f"\n\nReturn the response strictly as a JSON object matching this schema:\n"
            f"{schema.model_json_schema()}\n"
            f"Do not include any preambles, explanations, or extra text. Output ONLY the JSON."
        )
        full_prompt = prompt + json_instruction

        response_text = self.generate_text(full_prompt, system_prompt)
        cleaned_text = self._clean_json_response(response_text)

        try:
            return schema.model_validate_json(cleaned_text)
        except Exception as e:
            logger.error(f"Failed to parse Anthropic response into schema {schema.__name__}. Error: {e}")
            raise ValueError(f"JSON validation failed for schema {schema.__name__}: {e}") from e
