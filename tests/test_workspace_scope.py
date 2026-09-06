from pathlib import Path

from core.runtime.workspace import scoped_workspace
from core.runtime.permissions import get_workspace_root


def test_scoped_workspace_overrides_default_and_restores():
    before = get_workspace_root()
    target = Path(before) / ".friday" / "workspaces" / "test-scope"

    with scoped_workspace(target):
        assert get_workspace_root() == target.resolve()

    assert get_workspace_root() == before
