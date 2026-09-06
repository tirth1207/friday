"""Scoped GitHub Git-transport credentials for local repository workspaces."""
from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from typing import Iterator

from core.github_oauth import load_connection


@contextmanager
def git_auth_environment() -> Iterator[dict[str, str]]:
    """Provide temporary GitHub credentials without persisting tokens or putting them in argv."""
    connection = load_connection() or {}
    token = str(connection.get("access_token") or "").strip()
    env = os.environ.copy()
    if token:
        askpass = os.path.abspath(os.path.join(os.path.dirname(__file__), "github_askpass.py"))
        env["GIT_ASKPASS"] = askpass
        env["FRIDAY_GITHUB_TOKEN"] = token
        env["GIT_TERMINAL_PROMPT"] = "0"
    yield env


def clone_repository(repository: str, destination: str, branch: str | None = None) -> subprocess.CompletedProcess[str]:
    """Clone a GitHub repository using the active OAuth credential when available."""
    target = repository.strip()
    if target.startswith("https://github.com/") or target.startswith("http://github.com/"):
        url = target
    else:
        url = f"https://github.com/{target.removeprefix('/')}"

    command = ["git", "clone"]
    if branch:
        command.extend(["--branch", branch])
    command.extend([url, destination])

    with git_auth_environment() as env:
        return subprocess.run(command, capture_output=True, text=True, env=env, check=False)
