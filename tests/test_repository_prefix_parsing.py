from core.orchestrator_structured import _extract_repository_target


def test_concatenated_repository_prefix_is_parsed():
    assert _extract_repository_target(
        "Repositorytirth1207/AGI_Maze explain this project",
        "explain this project",
        selected_repository="tirth1207/Orbit",
    ) == "tirth1207/AGI_Maze"


def test_pronoun_request_uses_selected_repository():
    assert _extract_repository_target(
        "explain this project",
        "explain this project",
        selected_repository="tirth1207/DevNest",
    ) == "tirth1207/DevNest"
