import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


SKIP_SCHEMES = {"mailto", "tel", "javascript", "data"}
ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".css",
    ".js",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".ico",
    ".mp4",
    ".webm",
    ".zip",
    ".gz",
    ".tgz",
}


def is_supported_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_url(url: str, base_url: str | None = None) -> str:
    resolved = urljoin(base_url, url) if base_url else url
    parsed = urlparse(resolved)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunparse((scheme, netloc, path, "", query, ""))


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def same_domain(url_a: str, url_b: str) -> bool:
    return get_domain(url_a) == get_domain(url_b)


def within_prefix(url: str, prefix: str | None) -> bool:
    if not prefix:
        return True
    return normalize_url(url).startswith(normalize_url(prefix))


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme.lower() in SKIP_SCHEMES:
        return True
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in ASSET_EXTENSIONS)


def sanitize_filename(value: str, fallback: str = "document") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._")
    return cleaned[:120] or fallback
