from io import BytesIO

from pypdf import PdfReader

from app.services.markdown_service import MarkdownService


class PDFService:
    def __init__(self) -> None:
        self.markdown_service = MarkdownService()

    def extract_markdown(self, content: bytes, source_url: str) -> tuple[str, str, list[str]]:
        reader = PdfReader(BytesIO(content))
        sections: list[str] = []
        notes: list[str] = []

        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            normalized = self.markdown_service.wrap_plain_text(page_text)
            sections.append(f"## PDF Page {index}\n\n{normalized}")

        if not sections:
            notes.append("PDF extraction produced no text.")

        title = source_url.rstrip("/").split("/")[-1] or "document.pdf"
        markdown = "\n\n".join(sections) if sections else "_No text extracted from PDF._"
        return title, markdown, notes
