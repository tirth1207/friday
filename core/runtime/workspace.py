"""Scoped workspace selection for FRIDAY tool execution."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


_workspace_override: ContextVar[Path | None] = ContextVar("friday_workspace_override", default=None)


def get_scoped_workspace() -> Path | None:
    """Return the task-local repository workspace, if one is active."""
    return _workspace_override.get()


def _validate_repository_workspace(path: Path) -> Path:
    target = path.expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"Scoped workspace does not exist: {target}")
    if not (target / ".git").is_dir():
        raise ValueError(f"Scoped workspace is not a Git repository: {target}")
    return target


@contextmanager
def scoped_workspace(path: str | Path):
    """Route filesystem, Git and terminal tools to one isolated repository clone."""
    target = _validate_repository_workspace(Path(path))
    token = _workspace_override.set(target)
    try:
        yield target
    finally:
        _workspace_override.reset(token)
