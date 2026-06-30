import logging
import re

import httpx
from pydantic import BaseModel

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.local_agy")


class LocalAGYProvider(BaseLLMProvider):
    """
    Local AGY provider that interfaces with a local OpenAI-compatible endpoint.
    """

    def _clean_json_response(self, text: str) -> str:
        """
        Extracts JSON block from markdown tags if present, otherwise returns text.
        """
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        url = f"{self.api_url or 'http://localhost:8000/v1'}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model or "default",
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return str(result["choices"][0]["message"]["content"])
        except Exception as e:
            logger.error(f"Error calling Local AGY LLM: {e}")
            # Return a simple structured or unstructured failure fallback
            raise RuntimeError(f"Local AGY provider call failed: {e}") from e

    def generate_json(
        self, prompt: str, schema: type[BaseModel], system_prompt: str | None = None
    ) -> BaseModel:
        # Enhance prompt to request JSON matching the schema
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
            logger.error(
                f"Failed to parse LLM response into schema {schema.__name__}. Raw: {response_text}. Error: {e}"
            )
            # Try to regex parse if validation fails or raise
            raise ValueError(
                f"JSON validation failed for schema {schema.__name__}: {e}"
            ) from e
