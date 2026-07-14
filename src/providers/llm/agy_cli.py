import logging
import re
import subprocess
from pydantic import BaseModel

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.agy_cli")


class AGYCLIProvider(BaseLLMProvider):
    """
    Local AGY provider that executes the 'agy' CLI command directly.
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
        # Build prompt including system prompt if present
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            result = subprocess.run(
                ["agy", "--print", full_prompt],
                capture_output=True,
                text=True,
                timeout=300,
                cwd="/tmp",
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(
                    f"'agy' CLI command failed with code {result.returncode}. "
                    f"Stdout: {result.stdout.strip()} | Error: {result.stderr.strip()}"
                )
                raise RuntimeError(f"Local AGY CLI execution failed: {result.stderr or result.stdout}")
        except FileNotFoundError as fnf_err:
            logger.error(f"'agy' CLI not found in PATH: {fnf_err}")
            raise RuntimeError("The 'agy' CLI is not found in PATH.") from fnf_err
        except Exception as sub_err:
            logger.error(f"'agy' command execution failed: {sub_err}")
            raise RuntimeError(f"'agy' command execution failed: {sub_err}") from sub_err

    def generate_json(self, prompt: str, schema: type[BaseModel], system_prompt: str | None = None) -> BaseModel:
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
            raise ValueError(f"JSON validation failed for schema {schema.__name__}: {e}") from e
