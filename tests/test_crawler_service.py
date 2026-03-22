from app.services.crawler_service import CrawlerService
from app.services.fetch_service import FetchResult


class FakeFetchService:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch(self, url: str) -> FetchResult:
        html = self.pages[url]
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=html,
            content=html.encode(),
        )


def test_crawler_respects_depth_and_prefix() -> None:
    pages = {
        "https://example.com/docs": '<a href="/docs/page-1">One</a><a href="/blog">Blog</a>',
        "https://example.com/docs/page-1": '<a href="/docs/page-2">Two</a>',
        "https://example.com/docs/page-2": "<p>Done</p>",
    }
    crawler = CrawlerService()
    crawler.fetch_service = FakeFetchService(pages)

    crawled, warnings = crawler.crawl(
        "https://example.com/docs",
        allowed_prefix="https://example.com/docs",
        max_depth=1,
        max_pages=10,
        same_domain_only=True,
    )

    assert [page.normalized_url for page in crawled] == [
        "https://example.com/docs",
        "https://example.com/docs/page-1",
    ]
    assert any("outside crawl prefix" in warning for warning in warnings)
