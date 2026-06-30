import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """
    Gemini provider using Google Generative Language API.
    """

    def _clean_json_response(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        model_name = self.model or "gemini-1.5-flash"
        url = self.api_url or f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        contents = [{"role": "user", "parts": [{"text": prompt}]}]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload, params=params)
                response.raise_for_status()
                result = response.json()
                return str(result["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            raise RuntimeError(f"Gemini provider call failed: {e}") from e

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
            logger.error(f"Failed to parse Gemini response into schema {schema.__name__}. Error: {e}")
            raise ValueError(f"JSON validation failed for schema {schema.__name__}: {e}") from e
