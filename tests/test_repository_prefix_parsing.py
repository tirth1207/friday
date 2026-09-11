from core.main import _explicit_repository_from_message, _looks_like_file_path, _normalize_repository_context
from core.orchestrator_structured import _extract_repository_target


def test_concatenated_repository_prefix_is_parsed_at_chat_boundary():
    assert _explicit_repository_from_message(
        "Repositorytirth1207/AGI_Maze explain this project"
    ) == "tirth1207/AGI_Maze"


def test_chat_extracts_concatenated_repository_prefix_for_build_request():
    assert _explicit_repository_from_message(
        "Repositorytirth1207/friday commit one simple test/page.tsx"
    ) == "tirth1207/friday"


def test_chat_ignores_file_path_before_explicit_repository():
    assert _explicit_repository_from_message(
        "commit test/page.tsx in tirth1207/friday"
    ) == "tirth1207/friday"


def test_file_path_guard_matches_common_extensions():
    assert _looks_like_file_path("test/page.tsx")
    assert _looks_like_file_path("src/app/page.py")
    assert not _looks_like_file_path("tirth1207/friday")
    assert not _looks_like_file_path("tirth1207/AGI_Maze")


def test_chat_extracts_normal_repository_prefix():
    assert _explicit_repository_from_message(
        "Repository: tirth1207/friday commit one simple test/page.tsx"
    ) == "tirth1207/friday"


def test_structured_agent_uses_canonical_selected_repository_context():
    assert _extract_repository_target(
        "explain this project",
        "explain this project",
        selected_repository="tirth1207/DevNest",
    ) == "tirth1207/DevNest"


def test_repository_context_normalizes_concatenated_label():
    assert _normalize_repository_context("Repositorytirth1207/friday") == "tirth1207/friday"
