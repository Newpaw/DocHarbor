from app.services.url_utils import normalize_url, same_domain, should_skip_url, within_prefix


def test_normalize_url_sorts_query_and_drops_fragment() -> None:
    normalized = normalize_url("https://Example.com/docs/?b=2&a=1#intro")
    assert normalized == "https://example.com/docs?a=1&b=2"


def test_same_domain() -> None:
    assert same_domain("https://docs.example.com/a", "https://docs.example.com/b")
    assert not same_domain("https://docs.example.com/a", "https://example.com/b")


def test_within_prefix() -> None:
    assert within_prefix("https://example.com/docs/api", "https://example.com/docs")
    assert not within_prefix("https://example.com/blog", "https://example.com/docs")


def test_should_skip_assets_and_js_links() -> None:
    assert should_skip_url("javascript:void(0)")
    assert should_skip_url("https://example.com/app.js")
    assert not should_skip_url("https://example.com/docs")
