from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    content: bytes


class FetchService:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.fetch_timeout_seconds
        self.headers = {"User-Agent": settings.user_agent}

    def fetch(self, url: str) -> FetchResult:
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                text=response.text,
                content=response.content,
            )
