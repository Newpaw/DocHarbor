import re

from bs4 import BeautifulSoup, NavigableString, Tag

try:
    from markdownify import markdownify as to_markdown
except Exception:  # pragma: no cover
    to_markdown = None


class MarkdownService:
    def convert_html(self, html: str) -> str:
        if to_markdown is not None:
            markdown = to_markdown(
                html,
                heading_style="ATX",
                bullets="-",
                strip=["script", "style"],
            )
        else:
            markdown = self._fallback_convert(html)
        return self.normalize_markdown(markdown)

    def normalize_markdown(self, text: str) -> str:
        text = text.replace("\r\n", "\n").strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip()

    def wrap_plain_text(self, text: str) -> str:
        cleaned = self.normalize_markdown(text)
        return cleaned if cleaned else "_No content extracted._"

    def _fallback_convert(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.body or soup
        return self._render_children(root)

    def _render_children(self, node: Tag) -> str:
        parts: list[str] = []
        for child in node.children:
            rendered = self._render_node(child)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)

    def _render_node(self, node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            return str(node).strip()
        if not isinstance(node, Tag):
            return ""

        name = node.name.lower()
        if name in {"script", "style", "noscript"}:
            return ""
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            return f"{'#' * level} {node.get_text(' ', strip=True)}"
        if name == "pre":
            code = node.get_text("\n", strip=False).strip("\n")
            return f"```\n{code}\n```"
        if name == "code":
            return f"`{node.get_text(' ', strip=True)}`"
        if name in {"ul", "ol"}:
            items = []
            for index, child in enumerate(node.find_all("li", recursive=False), start=1):
                prefix = f"{index}. " if name == "ol" else "- "
                items.append(prefix + child.get_text(" ", strip=True))
            return "\n".join(items)
        if name == "a":
            text = node.get_text(" ", strip=True) or node.get("href", "")
            href = node.get("href", "")
            return f"[{text}]({href})" if href else text
        if name in {"p", "blockquote"}:
            return node.get_text(" ", strip=True)
        if name == "br":
            return "\n"
        return self._render_children(node)
