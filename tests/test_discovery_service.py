from app.services.brave_search_service import BraveSearchRateLimitError, SearchHit
from app.services.discovery_service import DiscoveryService


class FakeBraveService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def is_available(self) -> bool:
        return True

    def search(self, query: str, count: int = 5) -> list[SearchHit]:
        self.calls.append((query, count))
        if "documentation" in query:
            raise BraveSearchRateLimitError("rate limited")
        return [
            SearchHit(
                title="ElevenLabs Docs",
                url="https://elevenlabs.io/docs",
                description="Official documentation",
            ),
            SearchHit(
                title="ElevenLabs API Reference",
                url="https://elevenlabs.io/docs/api-reference/introduction",
                description="API reference",
            ),
        ]


def test_discovery_returns_partial_results_when_rate_limited() -> None:
    service = DiscoveryService()
    fake_brave = FakeBraveService()
    service.brave = fake_brave

    candidates = service.discover("ElevenLabs")

    assert candidates
    assert candidates[0].url.startswith("https://elevenlabs.io")
    assert fake_brave.calls == [("ElevenLabs official docs", 5), ("ElevenLabs documentation", 5)]
