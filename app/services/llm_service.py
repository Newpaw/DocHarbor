from __future__ import annotations

from collections.abc import Sequence

from app.config import get_settings

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.is_available():
            try:
                self._client = OpenAI(api_key=self.settings.openai_api_key)
            except Exception:  # pragma: no cover
                self._client = None

    def is_available(self) -> bool:
        return bool(self.settings.openai_api_key and OpenAI is not None)

    def classify_source_type(self, url: str, signals: Sequence[str], html_excerpt: str) -> str | None:
        if not self._client:
            return None
        prompt = (
            "Choose one label only: multi_page_docs, single_page_html, pdf, markdown, plain_text, unknown.\n"
            f"URL: {url}\nSignals: {'; '.join(signals)}\nExcerpt:\n{html_excerpt[:4000]}"
        )
        response = self._client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
        )
        text = getattr(response, "output_text", "").strip().lower()
        valid = {
            "multi_page_docs",
            "single_page_html",
            "pdf",
            "markdown",
            "plain_text",
            "unknown",
        }
        return text if text in valid else None
