from unittest.mock import MagicMock

from src.providers.browser import BrowserProvider


def test_search_google_redirect_cleaning():
    """Verify that search_google correctly parses and cleans different forms of DuckDuckGo redirect URLs."""
    provider = BrowserProvider()

    # Mock HTML containing different link formats
    mock_html = """
    <html>
        <body>
            <div class="result__body">
                <a class="result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.com%2Fcareers&rut=123">Example 1</a>
                <a class="result__snippet">Snippet 1</a>
            </div>
            <div class="result__body">
                <a class="result__url" href="/l/?uddg=https%3A%2F%2Fwww.test.com%2Fjobs&rut=456">Example 2</a>
                <a class="result__snippet">Snippet 2</a>
            </div>
            <div class="result__body">
                <a class="result__url" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.valid-url.com&rut=789">Example 3</a>
                <a class="result__snippet">Snippet 3</a>
            </div>
            <div class="result__body">
                <a class="result__url" href="//example.com/no-redirect">Example 4</a>
                <a class="result__snippet">Snippet 4</a>
            </div>
        </body>
    </html>
    """

    provider.fetch_page_http = MagicMock(return_value=mock_html)

    results = provider.search_google("dummy query", num_results=5)

    assert len(results) == 4
    assert results[0]["url"] == "https://www.example.com/careers"
    assert results[1]["url"] == "https://www.test.com/jobs"
    assert results[2]["url"] == "https://www.valid-url.com"
    assert results[3]["url"] == "https://example.com/no-redirect"
