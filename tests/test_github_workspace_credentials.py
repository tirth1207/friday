from pathlib import Path
from subprocess import CompletedProcess


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
    monkeypatch.setattr(workspace.settings, "friday_workspace", str(tmp_path))

    captured = {}

    def fake_run_process(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(workspace, "_run_process", fake_run_process)
    result = __import__("asyncio").run(workspace.prepare_repository_workspace("tirth1207/friday"))

    assert result["repository"] == "tirth1207/friday"
    assert "secret-test-token" not in " ".join(map(str, captured["command"]))
    assert captured["env"]["FRIDAY_GITHUB_TOKEN"] == "secret-test-token"
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert Path(captured["env"]["GIT_ASKPASS"]).name == "github_askpass.py"
