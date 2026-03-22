from app.services.markdown_service import MarkdownService


def test_markdown_service_preserves_heading_and_code() -> None:
    html = "<main><h1>Hello</h1><pre><code>print('x')</code></pre></main>"
    markdown = MarkdownService().convert_html(html)
    assert "# Hello" in markdown
    assert "print('x')" in markdown
