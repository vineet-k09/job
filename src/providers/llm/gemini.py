import logging
from typing import Any

import httpx

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """
    Gemini provider using Google Generative Language API.
    """

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

