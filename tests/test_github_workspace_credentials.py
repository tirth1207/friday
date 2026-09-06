from pathlib import Path


def test_workspace_clone_uses_ephemeral_git_auth(monkeypatch, tmp_path):
    from tools.git import workspace

    monkeypatch.setattr(
        workspace,
        "refresh_connection_if_needed",
        lambda: __import__("asyncio").sleep(0, result=True),
    )
    monkeypatch.setattr(
        workspace,
        "load_connection",
        lambda: {"access_token": "secret-test-token"},
    )

    captured = {}

    async def fake_create_subprocess_exec(*command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]

        class Process:
            returncode = 0

            async def communicate(self):
                return b"", b""

        return Process()

    monkeypatch.setattr(workspace.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    result = __import__("asyncio").run(workspace.prepare_repository_workspace("tirth1207/friday"))

    assert result["repository"] == "tirth1207/friday"
    assert "secret-test-token" not in " ".join(map(str, captured["command"]))
    assert captured["env"]["FRIDAY_GITHUB_TOKEN"] == "secret-test-token"
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert Path(captured["env"]["GIT_ASKPASS"]).name == "github_askpass.py"
