import logging

import httpx

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.local_agy")


class LocalAGYProvider(BaseLLMProvider):
    """
    Local AGY provider that interfaces with a local OpenAI-compatible endpoint.
    """

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        # Build prompt including system prompt if present
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

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
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            # Fall back to running local `agy` command
            logger.info(
                "Local HTTP LLM server connection refused. Falling back to executing local 'agy' CLI command..."
            )
            try:
                import subprocess

                result = subprocess.run(
                    ["agy", "--dangerously-skip-permissions", "--disable-slash-commands", "--print", full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd="/tmp",
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if not output and result.stderr.strip():
                        logger.warning(
                            f"Fallback 'agy' returned exit code 0 but stdout was empty. Stderr: {result.stderr.strip()}"
                        )
                    return output
                else:
                    logger.error(
                        f"Fallback 'agy' CLI command failed with code {result.returncode}. "
                        f"Stdout: {result.stdout.strip()} | Error: {result.stderr.strip()}"
                    )
                    raise RuntimeError(f"Local AGY CLI execution failed: {result.stderr or result.stdout}") from e
            except FileNotFoundError as fnf_err:
                logger.error(f"Fallback 'agy' CLI not found in PATH: {fnf_err}")
                raise RuntimeError("Local AGY HTTP connection refused and 'agy' CLI is not found in PATH.") from e
            except Exception as sub_err:
                logger.error(f"Fallback 'agy' command execution failed: {sub_err}")
                raise RuntimeError(f"Fallback 'agy' command execution failed: {sub_err}") from e
        except Exception as e:
            logger.error(f"Error calling Local AGY LLM API: {e}")
            raise RuntimeError(f"Local AGY provider call failed: {e}") from e

