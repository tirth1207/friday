import pytest

from core.proactive.attention import AttentionManager
from core.proactive.interests import Interest


def test_watcher_matching(monkeypatch, tmp_path):
    from core.proactive import osiris_watcher

    async def fake_news(query=""):
        return {
            "data": {
                "items": [
                    {
                        "title": "Max Verstappen takes pole",
                        "description": "Red Bull driver Max Verstappen leads the Formula 1 session.",
                        "url": "https://example.com/f1",
                        "published_at": "2026-09-21T10:00:00Z",
                    },
                    {
                        "title": "Unrelated technology story",
                        "description": "A software release happened today.",
                        "url": "https://example.com/tech",
                    },
                ]
            }
        }

    monkeypatch.setattr(osiris_watcher, "osiris_news", fake_news)
    import asyncio
    signals = asyncio.run(
        osiris_watcher.poll_interest(
            Interest("Formula 1", ("Formula 1", "Max Verstappen", "Red Bull")),
            AttentionManager(str(tmp_path / "proactive.db")),
        )
    )
    assert len(signals) == 1
    assert "Max Verstappen" in signals[0].title
