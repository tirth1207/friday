from core.main import _explicit_repository_from_message, _normalize_repository_context
from core.orchestrator_structured import _extract_repository_target


def test_concatenated_repository_prefix_is_parsed():
    assert _extract_repository_target(
        "Repositorytirth1207/AGI_Maze explain this project",
        "explain this project",
        selected_repository="tirth1207/Orbit",
    ) == "tirth1207/AGI_Maze"


def test_chat_extracts_concatenated_repository_prefix():
    assert _explicit_repository_from_message(
        "Repositorytirth1207/friday commit one simple test/page.tsx"
    ) == "tirth1207/friday"


def test_chat_extracts_normal_repository_prefix():
    assert _explicit_repository_from_message(
        "Repository: tirth1207/friday commit one simple test/page.tsx"
    ) == "tirth1207/friday"


def test_pronoun_request_uses_selected_repository():
    assert _extract_repository_target(
        "explain this project",
        "explain this project",
        selected_repository="tirth1207/DevNest",
    ) == "tirth1207/DevNest"


def test_repository_context_normalizes_concatenated_label():
    assert _normalize_repository_context("Repositorytirth1207/friday") == "tirth1207/friday"
