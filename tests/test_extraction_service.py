from app.services.extraction_service import ExtractionService


def test_extraction_removes_navigation_noise() -> None:
    html = """
    <html>
      <head><title>Guide</title></head>
      <body>
        <nav>Top Nav</nav>
        <main>
          <h1>Install</h1>
          <p>Run this command.</p>
          <pre><code>uv sync</code></pre>
        </main>
        <footer>Footer</footer>
      </body>
    </html>
    """
    result = ExtractionService().extract_html(html, "https://example.com/docs")
    assert "Top Nav" not in result.markdown
    assert "Footer" not in result.markdown
    assert "Install" in result.markdown
    assert "uv sync" in result.markdown
