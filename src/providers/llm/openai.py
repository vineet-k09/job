
from src.providers.llm.local_agy import LocalAGYProvider


class OpenAIProvider(LocalAGYProvider):
    """
    OpenAI provider using OpenAI's API.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo",
        api_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ):
        url = api_url or "https://api.openai.com/v1"
        super().__init__(
            api_key=api_key,
            model=model,
            api_url=url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
