import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from rich.logging import RichHandler

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """
    Format logs as a single-line JSON string containing metadata.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Inject standard pipeline fields if present
        for field in [
            "run_id",
            "company",
            "stage",
            "duration_seconds",
            "status",
            "errors",
            "retries",
        ]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
            elif isinstance(record.args, dict) and field in record.args:
                log_data[field] = record.args[field]

        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    parent_logger = logging.getLogger("recruiting-platform")
    parent_logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if parent logger is already configured
    if not parent_logger.handlers:
        # Console Handler with Rich
        console_handler = RichHandler(rich_tracebacks=True, markup=True, show_path=False)
        console_handler.setLevel(logging.INFO)

        # File Handler (structured JSON logs)
        file_handler = logging.FileHandler("logs/platform.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)

        parent_logger.addHandler(console_handler)
        parent_logger.addHandler(file_handler)

    return logging.getLogger(name)


class PipelineLogger:
    """
    Adapter for logger to inject pipeline state (run_id, stage, company, etc.) automatically.
    """

    def __init__(
        self,
        logger: logging.Logger,
        run_id: str,
        stage: str | None = None,
        company: str | None = None,
    ):
        self.logger = logger
        self.run_id = run_id
        self.stage = stage
        self.company = company

    def info(
        self,
        msg: str,
        duration: float | None = None,
        status: str | None = None,
        retries: int | None = None,
        errors: str | None = None,
    ) -> None:
        extra = {
            "run_id": self.run_id,
            "stage": self.stage,
            "company": self.company,
            "duration_seconds": duration,
            "status": status,
            "retries": retries,
            "errors": errors,
        }
        self.logger.info(msg, extra=extra)

    def error(
        self,
        msg: str,
        duration: float | None = None,
        status: str | None = None,
        retries: int | None = None,
        errors: str | None = None,
    ) -> None:
        extra = {
            "run_id": self.run_id,
            "stage": self.stage,
            "company": self.company,
            "duration_seconds": duration,
            "status": status,
            "retries": retries,
            "errors": errors,
        }
        self.logger.error(msg, extra=extra)

    def debug(
        self,
        msg: str,
        duration: float | None = None,
        status: str | None = None,
        retries: int | None = None,
        errors: str | None = None,
    ) -> None:
        extra = {
            "run_id": self.run_id,
            "stage": self.stage,
            "company": self.company,
            "duration_seconds": duration,
            "status": status,
            "retries": retries,
            "errors": errors,
        }
        self.logger.debug(msg, extra=extra)

    def warning(
        self,
        msg: str,
        duration: float | None = None,
        status: str | None = None,
        retries: int | None = None,
        errors: str | None = None,
    ) -> None:
        extra = {
            "run_id": self.run_id,
            "stage": self.stage,
            "company": self.company,
            "duration_seconds": duration,
            "status": status,
            "retries": retries,
            "errors": errors,
        }
        self.logger.warning(msg, extra=extra)
