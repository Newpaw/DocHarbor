from dataclasses import dataclass
from typing import ClassVar

import httpx

from app.config import get_settings


@dataclass
class SearchHit:
    title: str
    url: str
    description: str


class BraveSearchRateLimitError(RuntimeError):
    pass


class BraveSearchService:
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    _cache: ClassVar[dict[tuple[str, int], list[SearchHit]]] = {}

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_available(self) -> bool:
        return bool(self.settings.brave_search_api_key)

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        if not self.is_available():
            return []

        cache_key = (query.strip().lower(), count)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.settings.brave_search_api_key,
        }
        params = {"q": query, "count": count}
        with httpx.Client(timeout=self.settings.fetch_timeout_seconds) as client:
            response = client.get(self.BASE_URL, headers=headers, params=params)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                hint = f" Retry after {retry_after} seconds." if retry_after else ""
                raise BraveSearchRateLimitError(
                    "Brave Search rate limit reached on the free tier."
                    " Wait briefly, try again, or use a direct URL."
                    f"{hint}"
                )
            response.raise_for_status()
            data = response.json()

        results = data.get("web", {}).get("results", [])
        hits: list[SearchHit] = []
        for item in results:
            hits.append(
                SearchHit(
                    title=item.get("title", item.get("url", "")),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                )
            )
        self._cache[cache_key] = hits
        return hits
