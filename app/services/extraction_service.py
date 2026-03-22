from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from app.services.markdown_service import MarkdownService


@dataclass
class ExtractionResult:
    title: str
    markdown: str
    notes: list[str]


class ExtractionService:
    NOISE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "aside",
        "script",
        "style",
        "noscript",
        "form",
        "button",
        "[role='navigation']",
        ".sidebar",
        ".toc",
        ".table-of-contents",
        ".breadcrumbs",
        ".search",
        ".theme-toggle",
        ".pagination",
        ".cookie",
    ]

    CONTENT_SELECTORS = [
        "main",
        "article",
        "[role='main']",
        ".main-content",
        ".content",
        ".content-body",
        ".documentation",
        ".docs-content",
        ".markdown-body",
    ]

    def __init__(self) -> None:
        self.markdown_service = MarkdownService()

    def extract_html(self, html: str, source_url: str) -> ExtractionResult:
        soup = BeautifulSoup(html, "html.parser")
        notes: list[str] = []
        title = self._extract_title(soup, source_url)

        for selector in self.NOISE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        content_node = self._pick_content_node(soup)
        if content_node is None:
            notes.append("Fell back to <body> because no main content node was detected.")
            content_node = soup.body or soup

        for img in content_node.select("img"):
            img.decompose()

        markdown = self.markdown_service.convert_html(str(content_node))
        if not markdown.strip():
            notes.append("Markdown conversion produced empty content.")
            markdown = "_No meaningful content extracted._"

        return ExtractionResult(title=title, markdown=markdown, notes=notes)

    def extract_markdown(self, text: str, source_url: str) -> ExtractionResult:
        title = source_url.rstrip("/").split("/")[-1] or source_url
        markdown = self.markdown_service.normalize_markdown(text)
        return ExtractionResult(title=title, markdown=markdown, notes=[])

    def extract_plain_text(self, text: str, source_url: str) -> ExtractionResult:
        title = source_url.rstrip("/").split("/")[-1] or source_url
        markdown = self.markdown_service.wrap_plain_text(text)
        return ExtractionResult(title=title, markdown=markdown, notes=["Processed as plain text."])

    def _extract_title(self, soup: BeautifulSoup, source_url: str) -> str:
        if soup.title and soup.title.text.strip():
            return soup.title.text.strip()
        first_h1 = soup.find("h1")
        if first_h1 and first_h1.text.strip():
            return first_h1.text.strip()
        return source_url

    def _pick_content_node(self, soup: BeautifulSoup) -> Tag | None:
        candidates: list[Tag] = []
        for selector in self.CONTENT_SELECTORS:
            candidates.extend([node for node in soup.select(selector) if isinstance(node, Tag)])
        if not candidates:
            return None
        return max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
