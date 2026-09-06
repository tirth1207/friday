import pytest

import tools  # registers tools
from core.runtime.executor import tool_executor
from tools.github import repository_agent
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


@pytest.mark.asyncio
async def test_one_part_repository_name_uses_accessible_index(monkeypatch):
    monkeypatch.setattr(repository_agent.settings, "username", "tirth1207")
    monkeypatch.setattr(repository_agent.settings, "pat", "test-token")

    requested_paths = []

    async def fake_request(path, params=None):
        requested_paths.append((path, params))
        if path == "/user/repos":
            return [
                {"name": "Orbit", "full_name": "tirth1207/Orbit"},
                {"name": "minor_project-TPO", "full_name": "tirth1207/minor_project-TPO"},
            ]
        raise AssertionError(f"unexpected GitHub request: {path}")

    monkeypatch.setattr(repository_agent, "_request", fake_request)

    assert await repository_agent._resolve_repository("orbit") == "tirth1207/Orbit"
    assert requested_paths[0][0] == "/user/repos"


@pytest.mark.asyncio
async def test_private_repository_name_resolves_without_direct_case_sensitive_lookup(monkeypatch):
    monkeypatch.setattr(repository_agent.settings, "username", "tirth1207")
    monkeypatch.setattr(repository_agent.settings, "pat", "test-token")

    requested_paths = []

    async def fake_request(path, params=None):
        requested_paths.append((path, params))
        if path == "/user/repos":
            return [{"name": "minor_project-TPO", "full_name": "tirth1207/minor_project-TPO"}]
        raise AssertionError(f"unexpected GitHub request: {path}")

    monkeypatch.setattr(repository_agent, "_request", fake_request)

    assert await repository_agent._resolve_repository("minor_project-tpo") == "tirth1207/minor_project-TPO"
    assert requested_paths == [requested_paths[0]]
