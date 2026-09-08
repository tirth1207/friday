import pytest

from core.memory.context import resolve_request
from core.memory.memory import MemoryStore


def test_profile_memory_recall_is_scored_and_deduplicated(tmp_path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    first = store.remember_profile("coding_style", "Prefer TypeScript with strict typing", "remember that")
    duplicate = store.remember_profile("coding_style", "Prefer TypeScript with strict typing", "remember that again")

    assert first["existing"] is False
    assert duplicate["existing"] is True
    matches = store.recall_profile("typescript strict")
    assert len(matches) == 1
    assert matches[0]["category"] == "coding_style"


@pytest.mark.parametrize(
    "message, expected_fragment",
    [
        ("research the latest Python 3.14 changes", "research.web.search"),
        ("browse https://example.com", "browser.navigate"),
        ("play some music on Spotify", "music.*"),
    ],
)
def test_new_capabilities_are_marked_as_tool_tasks(message, expected_fragment):
    resolved = resolve_request(message)["resolved_request"]
    assert expected_fragment in resolved
