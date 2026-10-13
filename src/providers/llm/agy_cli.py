import logging
import subprocess

from src.providers.llm.base import BaseLLMProvider

logger = logging.getLogger("recruiting-platform.llm.agy_cli")


class AGYCLIProvider(BaseLLMProvider):
    """
    Local AGY provider that executes the 'agy' CLI command directly.
    """

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        # Build prompt including system prompt if present
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
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
                        f"'agy' returned exit code 0 but stdout was empty. Stderr: {result.stderr.strip()}"
                    )
                return output
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

