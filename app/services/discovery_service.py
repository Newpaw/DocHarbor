from urllib.parse import urlparse

from app.models import DiscoveryCandidate
from app.services.brave_search_service import BraveSearchRateLimitError, BraveSearchService


class DiscoveryService:
    QUERY_COUNT = 5

    def __init__(self) -> None:
        self.brave = BraveSearchService()

    def is_available(self) -> bool:
        return self.brave.is_available()

    def discover(self, software_name: str) -> list[DiscoveryCandidate]:
        queries = [
            f"{software_name} official docs",
            f"{software_name} documentation",
        ]

        ranked: dict[str, DiscoveryCandidate] = {}
        for query in queries:
            try:
                hits = self.brave.search(query, count=self.QUERY_COUNT)
            except BraveSearchRateLimitError:
                if ranked:
                    break
                raise

            for hit in hits:
                if not hit.url:
                    continue
                candidate = self._rank_candidate(software_name, hit.title, hit.url, hit.description)
                existing = ranked.get(candidate.url)
                if existing is None or candidate.confidence_score > existing.confidence_score:
                    ranked[candidate.url] = candidate
            if self._enough_candidates(ranked.values()):
                break

        ordered = sorted(ranked.values(), key=lambda item: item.confidence_score, reverse=True)
        return ordered[:8]

    def _enough_candidates(self, candidates: list[DiscoveryCandidate] | object) -> bool:
        items = list(candidates)
        strong = [candidate for candidate in items if candidate.confidence_score >= 0.55]
        return len(items) >= 5 and len(strong) >= 3

    def _rank_candidate(
        self,
        software_name: str,
        title: str,
        url: str,
        description: str,
    ) -> DiscoveryCandidate:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        url_lower = url.lower()
        title_lower = title.lower()
        software_lower = software_name.lower()

        score = 0.1
        reasons: list[str] = []
        official = software_lower.replace(" ", "") in domain.replace("-", "").replace(".", "")
        if official:
            score += 0.3
            reasons.append("Domain closely matches the software name.")

        if any(token in url_lower for token in ("/docs", "/documentation", "/developers", "/api", "/reference")):
            score += 0.35
            reasons.append("URL path looks documentation-oriented.")

        if any(token in title_lower for token in ("docs", "documentation", "api", "reference", "developer")):
            score += 0.2
            reasons.append("Title contains technical documentation keywords.")

        if "blog" in url_lower or "tutorial" in url_lower:
            score -= 0.2
            reasons.append("Lowered score because the URL looks like secondary content.")

        likely_type = "multi_page_docs" if any(
            token in url_lower for token in ("/docs", "/documentation", "/reference")
        ) else "single_page_html"

        return DiscoveryCandidate(
            title=title,
            url=url,
            domain=domain,
            reason=" ".join(reasons) or description or "Matched the discovery query.",
            confidence_score=max(min(score, 0.99), 0.05),
            likely_source_type=likely_type,
            appears_official=official,
        )
