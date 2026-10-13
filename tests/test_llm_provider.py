import pytest
from pydantic import BaseModel

from src.providers.llm.base import BaseLLMProvider


class SampleSchema(BaseModel):
    name: str
    count: int


class DummyLLMProvider(BaseLLMProvider):
    def __init__(self, responses: list[str]):
        super().__init__(api_key="", model="dummy")
        self.responses = list(responses)
        self.call_count = 0

    def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return ""


def test_json_extraction_valid():
    provider = DummyLLMProvider(['```json\n{"name": "test", "count": 5}\n```'])
    result = provider.generate_json("test prompt", SampleSchema)
    assert isinstance(result, SampleSchema)
    assert result.name == "test"
    assert result.count == 5


def test_json_extraction_raw_text():
    provider = DummyLLMProvider(['Here is the JSON: {"name": "hello", "count": 10} hope it helps'])
    result = provider.generate_json("test prompt", SampleSchema)
    assert result.name == "hello"
    assert result.count == 10


def test_retry_on_empty_and_transient_failure():
    # Attempt 1 returns empty, Attempt 2 returns invalid JSON, Attempt 3 returns valid JSON
    provider = DummyLLMProvider([
        "",
        "invalid json text",
        '{"name": "success", "count": 42}'
    ])
    result = provider.generate_json("test prompt", SampleSchema, max_retries=3)
    assert result.name == "success"
    assert result.count == 42
    assert provider.call_count == 3


def test_failure_after_max_retries():
    provider = DummyLLMProvider(["", "", "bad json"])
    with pytest.raises(ValueError, match="JSON validation failed for schema SampleSchema"):
        provider.generate_json("test prompt", SampleSchema, max_retries=3)
    assert provider.call_count == 3
