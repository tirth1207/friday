from tools.github.repository_agent import _match_repository


def test_repository_name_matches_case_insensitively():
    repositories = [
        {"name": "Orbit", "full_name": "tirth1207/Orbit"},
        {"name": "minor_project-TPO", "full_name": "tirth1207/minor_project-TPO"},
        {"name": "ai_Test", "full_name": "tirth1207/ai_Test"},
    ]

    assert _match_repository(repositories, "orbit")["full_name"] == "tirth1207/Orbit"
    assert _match_repository(repositories, "MINOR_PROJECT-TPO")["full_name"] == "tirth1207/minor_project-TPO"
    assert _match_repository(repositories, "ai_test")["full_name"] == "tirth1207/ai_Test"


def test_repository_name_matches_normalized_punctuation():
    repositories = [{"name": "minor_project-TPO", "full_name": "tirth1207/minor_project-TPO"}]

    assert _match_repository(repositories, "minor-project-tpo")["full_name"] == "tirth1207/minor_project-TPO"


def test_repository_name_returns_none_when_missing():
    repositories = [{"name": "Orbit", "full_name": "tirth1207/Orbit"}]

    assert _match_repository(repositories, "does-not-exist") is None
