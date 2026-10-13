import logging
import re
import time
from abc import ABC, abstractmethod

from pydantic import BaseModel

logger = logging.getLogger("recruiting-platform.llm.base")


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for LLM providers.
    Ensures a consistent interface across OpenAI, Anthropic, Gemini, and Local AGY.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        api_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Sends a standard text generation request to the LLM.
        """
        pass

    def _clean_json_response(self, text: str) -> str:
        """
        Extracts JSON block from markdown tags if present, or finds the outermost JSON object/array, otherwise returns text.
        """
        if not text:
            return ""

        # 1. First look for markdown code blocks ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()

        text = text.strip()
        # 2. If valid JSON directly, return it
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            return text

        # 3. Try to extract outermost JSON object or array using regex
        obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if obj_match:
            return obj_match.group(1).strip()

        return text

    def generate_json(
        self,
        prompt: str,
        schema: type[BaseModel],
        system_prompt: str | None = None,
        max_retries: int = 3,
    ) -> BaseModel:
        """
        Sends a request to the LLM and parses the response into the specified Pydantic schema with retry logic.
        """
        json_instruction = (
            f"\n\nReturn the response strictly as a JSON object matching this schema:\n"
            f"{schema.model_json_schema()}\n"
            f"Do not include any preambles, explanations, or extra text. Output ONLY the JSON."
        )
        full_prompt = prompt + json_instruction

        last_error: Exception | None = None
        last_raw_text = ""

        for attempt in range(1, max_retries + 1):
            try:
                response_text = self.generate_text(full_prompt, system_prompt)
                last_raw_text = response_text
                cleaned_text = self._clean_json_response(response_text)
                if not cleaned_text:
                    raise ValueError("LLM returned an empty response")
                return schema.model_validate_json(cleaned_text)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed to parse LLM response into schema {schema.__name__}. "
                    f"Raw: '{last_raw_text}'. Error: {e}"
                )
                if attempt < max_retries:
                    time.sleep(1)

        logger.error(
            f"Failed to parse LLM response into schema {schema.__name__} after {max_retries} attempts. "
            f"Raw: '{last_raw_text}'. Error: {last_error}"
        )
        raise ValueError(f"JSON validation failed for schema {schema.__name__}: {last_error}") from last_error

