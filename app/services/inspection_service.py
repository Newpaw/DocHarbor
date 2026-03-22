from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.schemas import InspectionResult
from app.services.fetch_service import FetchResult, FetchService
from app.services.llm_service import LLMService
from app.services.url_utils import get_domain, normalize_url


@dataclass
class InspectionSignals:
    detected_source_type: str
    confidence: float
    reasoning: list[str]
    recommended_ingestion_strategy: str
    recommended_crawl_prefix: str | None


class InspectionService:
    def __init__(self) -> None:
        self.fetch_service = FetchService()
        self.llm_service = LLMService()

    def inspect_source(self, url: str) -> InspectionResult:
        response = self.fetch_service.fetch(url)
        normalized_url = normalize_url(response.final_url)
        signals = self._classify(normalized_url, response)
        return InspectionResult(
            selected_url=url,
            normalized_url=normalized_url,
            detected_source_type=signals.detected_source_type,
            confidence=signals.confidence,
            reasoning=signals.reasoning,
            recommended_ingestion_strategy=signals.recommended_ingestion_strategy,
            recommended_crawl_prefix=signals.recommended_crawl_prefix,
        )

    def _classify(self, url: str, response: FetchResult) -> InspectionSignals:
        reasoning: list[str] = []
        content_type = response.content_type
        lower_url = url.lower()

        if content_type == "application/pdf" or lower_url.endswith(".pdf"):
            reasoning.append("Detected PDF content-type or URL suffix.")
            return InspectionSignals("pdf", 0.99, reasoning, "pdf", None)

        if "markdown" in content_type or lower_url.endswith((".md", ".mdx")):
            reasoning.append("Detected Markdown content-type or file extension.")
            return InspectionSignals("markdown", 0.98, reasoning, "markdown", None)

        if content_type.startswith("text/plain") or lower_url.endswith(".txt"):
            reasoning.append("Detected plain text content-type or URL suffix.")
            return InspectionSignals("plain_text", 0.95, reasoning, "plain_text", None)

        if "html" not in content_type and not content_type.startswith("text/"):
            reasoning.append(f"Unsupported or mixed content-type {content_type or 'unknown'}.")
            return InspectionSignals("unknown", 0.35, reasoning, "single_page_html", None)

        soup = BeautifulSoup(response.text, "html.parser")
        doc_links = []
        all_links = []
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            all_links.append(href)
            href_lower = href.lower()
            if any(token in href_lower for token in ("/docs", "/documentation", "/reference", "/api", "/guide")):
                doc_links.append(href)

        if soup.select("nav, aside, [role='navigation'], .sidebar, .toc, .table-of-contents"):
            reasoning.append("Found documentation-style navigation elements.")

        if len(doc_links) >= 5 or (len(all_links) >= 10 and len(doc_links) / max(len(all_links), 1) > 0.25):
            reasoning.append("Internal link density suggests a multi-page docs site.")
            prefix = self._recommend_prefix(url)
            return InspectionSignals("multi_page_docs", 0.84, reasoning, "multi_page_docs", prefix)

        if soup.find("article") or soup.find("main"):
            reasoning.append("Found a single main content region.")
            return InspectionSignals("single_page_html", 0.78, reasoning, "single_page_html", None)

        reasoning.append("HTML detected, but structure is ambiguous.")
        llm_guess = self.llm_service.classify_source_type(url, reasoning, response.text[:3000])
        if llm_guess:
            reasoning.append("OpenAI fallback used for ambiguous HTML classification.")
            strategy = llm_guess if llm_guess != "unknown" else "single_page_html"
            prefix = self._recommend_prefix(url) if llm_guess == "multi_page_docs" else None
            return InspectionSignals(llm_guess, 0.62, reasoning, strategy, prefix)

        return InspectionSignals("single_page_html", 0.55, reasoning, "single_page_html", None)

    def _recommend_prefix(self, url: str) -> str:
        domain = get_domain(url)
        for part in ("/docs", "/documentation", "/reference", "/api", "/developer", "/developers"):
            if part in url:
                return url[: url.index(part) + len(part)]
        return f"{url.split(domain, maxsplit=1)[0]}{domain}"
