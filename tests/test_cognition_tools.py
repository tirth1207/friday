from core.memory.memory import MemoryStore
from tools.cognition.cognition_tools import curiosity_probe


def test_curiosity_probe_is_bounded_and_actionable():
    result = curiosity_probe("finish the web app", "chat and GitHub already work", 4)
    assert result["goal"] == "finish the web app"
    assert len(result["questions"]) == 4
    assert all(question.endswith("?") for question in result["questions"])


def test_memory_store_supports_reusable_experiences(tmp_path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    store.add_experience({
        "kind": "lesson",
        "title": "Repository context",
        "lesson": "Explicit request context must override persisted defaults.",
        "context": "GitHub chat routing",
        "timestamp": "2026-09-06T00:00:00+00:00",
    })
    matches = store.search_experiences("repository context")
    assert matches
    assert matches[0]["title"] == "Repository context"
