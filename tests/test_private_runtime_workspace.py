from pathlib import Path


def test_default_workspace_is_outside_source_repository(monkeypatch):
    from core import config

    monkeypatch.delenv("FRIDAY_WORKSPACE", raising=False)
    root = Path(config.get_default_workspace())

    if config.platform.system() == "Windows":
        assert root == Path(r"C:\.friday")
    else:
        assert root == Path.home() / ".friday"


def test_configured_workspace_is_used(monkeypatch, tmp_path):
    monkeypatch.setenv("FRIDAY_WORKSPACE", str(tmp_path))
    assert Path(__import__("core.config", fromlist=["get_default_workspace"]).get_default_workspace()) == tmp_path.resolve()
