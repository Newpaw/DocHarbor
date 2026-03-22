from collections import deque
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.services.fetch_service import FetchResult, FetchService
from app.services.url_utils import normalize_url, same_domain, should_skip_url, within_prefix


@dataclass
class CrawlPage:
    source_url: str
    normalized_url: str
    depth: int
    response: FetchResult
    child_links: list[str]


class CrawlerService:
    def __init__(self) -> None:
        self.fetch_service = FetchService()

    def crawl(
        self,
        start_url: str,
        *,
        allowed_prefix: str | None,
        max_depth: int,
        max_pages: int,
        same_domain_only: bool,
    ) -> tuple[list[CrawlPage], list[str]]:
        queue: deque[tuple[str, int]] = deque([(normalize_url(start_url), 0)])
        seen: set[str] = set()
        pages: list[CrawlPage] = []
        warnings: list[str] = []

        while queue and len(pages) < max_pages:
            current_url, depth = queue.popleft()
            if current_url in seen or depth > max_depth:
                continue
            seen.add(current_url)

            if should_skip_url(current_url):
                warnings.append(f"Skipped asset-like URL: {current_url}")
                continue

            if allowed_prefix and not within_prefix(current_url, allowed_prefix):
                warnings.append(f"Skipped URL outside crawl prefix: {current_url}")
                continue

            if same_domain_only and not same_domain(start_url, current_url):
                warnings.append(f"Skipped cross-domain URL: {current_url}")
                continue

            try:
                response = self.fetch_service.fetch(current_url)
            except Exception as exc:
                warnings.append(f"Failed to fetch {current_url}: {exc}")
                continue

            links = self._extract_links(response.text, response.final_url)
            pages.append(
                CrawlPage(
                    source_url=current_url,
                    normalized_url=normalize_url(response.final_url),
                    depth=depth,
                    response=response,
                    child_links=links,
                )
            )

            for link in links:
                normalized = normalize_url(link, response.final_url)
                if normalized not in seen:
                    queue.append((normalized, depth + 1))

        return pages, warnings

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for tag in soup.select("a[href]"):
            href = tag.get("href", "").strip()
            if not href or href.startswith("#") or should_skip_url(href):
                continue
            links.append(normalize_url(href, base_url))
        return links
