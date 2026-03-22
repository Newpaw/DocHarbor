from app.services.fetch_service import FetchResult
from app.services.inspection_service import InspectionService


class StubFetchService:
    def __init__(self, result: FetchResult) -> None:
        self.result = result

    def fetch(self, url: str) -> FetchResult:
        return self.result


def test_inspection_detects_pdf() -> None:
    service = InspectionService()
    service.fetch_service = StubFetchService(
        FetchResult(
            url="https://example.com/file.pdf",
            final_url="https://example.com/file.pdf",
            status_code=200,
            content_type="application/pdf",
            text="",
            content=b"%PDF-1.4",
        )
    )
    result = service.inspect_source("https://example.com/file.pdf")
    assert result.detected_source_type == "pdf"
    assert result.recommended_ingestion_strategy == "pdf"


def test_inspection_detects_multi_page_docs() -> None:
    html = """
    <html><body>
      <nav><a href="/docs/start">Start</a></nav>
      <main><a href="/docs/install">Install</a><a href="/docs/api">API</a><a href="/docs/guide">Guide</a><a href="/docs/ref">Ref</a><a href="/docs/auth">Auth</a></main>
    </body></html>
    """
    service = InspectionService()
    service.fetch_service = StubFetchService(
        FetchResult(
            url="https://example.com/docs",
            final_url="https://example.com/docs",
            status_code=200,
            content_type="text/html",
            text=html,
            content=html.encode(),
        )
    )
    result = service.inspect_source("https://example.com/docs")
    assert result.detected_source_type == "multi_page_docs"
    assert result.recommended_crawl_prefix == "https://example.com/docs"
