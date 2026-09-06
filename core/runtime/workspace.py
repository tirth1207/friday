"""Scoped workspace selection for FRIDAY tool execution."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


_workspace_override: ContextVar[Path | None] = ContextVar("friday_workspace_override", default=None)


def get_scoped_workspace() -> Path | None:
    """Return the task-local workspace override, if one is active."""
    return _workspace_override.get()


@contextmanager
def scoped_workspace(path: str | Path):
    """Route filesystem, Git and terminal tools to one isolated workspace."""
    target = Path(path).resolve()
    token = _workspace_override.set(target)
    try:
        yield target
    finally:
        _workspace_override.reset(token)
