import pytest

from core import github_diagnostics


@pytest.mark.asyncio
async def test_diagnostic_calls_github_directly(monkeypatch):
    monkeypatch.setattr(
        github_diagnostics,
        "load_connection",
        lambda: {"access_token": "test-token"},
    )

    calls = []

    async def fake_request(token, path):
        calls.append((token, path))
        if path == "/repos/tirth1207/Orbit":
            return 200, "OK", {"default_branch": "main"}, None
        return 200, "OK", {"ok": True}, "contents=read"

    monkeypatch.setattr(github_diagnostics, "_request", fake_request)
    result = await github_diagnostics.run_github_diagnostic("contents", "tirth1207/Orbit")

    assert result["ok"] is True
    assert result["status"] == 200
    assert calls == [
        ("test-token", "/repos/tirth1207/Orbit"),
        ("test-token", "/repos/tirth1207/Orbit/contents?ref=main"),
    ]
    assert result["accepted_permissions"] == "contents=read"
    assert "LLM" in result["note"]


@pytest.mark.asyncio
async def test_diagnostic_reports_github_failure(monkeypatch):
    monkeypatch.setattr(
        github_diagnostics,
        "load_connection",
        lambda: {"access_token": "test-token"},
    )

    async def fake_request(token, path):
        return 403, "Forbidden", {"message": "Resource not accessible by integration"}, "contents=read"

    monkeypatch.setattr(github_diagnostics, "_request", fake_request)
    result = await github_diagnostics.run_github_diagnostic("metadata", "tirth1207/Orbit")

    assert result["ok"] is False
    assert result["status"] == 403
    assert result["message"] == "Resource not accessible by integration"
    assert result["accepted_permissions"] == "contents=read"


@pytest.mark.asyncio
async def test_diagnostic_requires_connection(monkeypatch):
    monkeypatch.setattr(github_diagnostics, "load_connection", lambda: None)

    with pytest.raises(github_diagnostics.GitHubDiagnosticError, match="not connected"):
        await github_diagnostics.run_github_diagnostic("identity")
