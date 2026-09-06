"""Scoped GitHub Git-transport credentials for local repository workspaces."""
from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlsplit, urlunsplit

from core.github_oauth import load_connection


def authenticated_clone_url(repository: str) -> str:
    """Build a token-authenticated HTTPS clone URL without exposing the token in callers."""
    target = repository.strip()
    if not target.startswith(("https://github.com/", "http://github.com/")):
        target = f"https://github.com/{target.removeprefix('/')}"
    parsed = urlsplit(target)
    token = str((load_connection() or {}).get("access_token") or "").strip()
    if not token:
        return target
    return urlunsplit((parsed.scheme, f"x-access-token:{token}@{parsed.netloc}", parsed.path, parsed.query, parsed.fragment))


@contextmanager
def git_auth_environment() -> Iterator[dict[str, str]]:
    """Provide temporary environment credentials for Git without writing tokens to disk."""
    connection = load_connection() or {}
    token = str(connection.get("access_token") or "").strip()
    env = os.environ.copy()
    if not token:
        yield env
        return

    # GIT_ASKPASS keeps the token out of the clone command itself and avoids credential persistence.
    askpass = os.path.abspath(os.path.join(os.path.dirname(__file__), "github_askpass.py"))
    env["GIT_ASKPASS"] = askpass
    env["FRIDAY_GITHUB_TOKEN"] = token
    env["GIT_TERMINAL_PROMPT"] = "0"
    yield env


def clone_repository(repository: str, destination: str, branch: str | None = None) -> subprocess.CompletedProcess[str]:
    """Clone a GitHub repository using the active OAuth credential when available."""
    url = authenticated_clone_url(repository)
    command = ["git", "clone"]
    if branch:
        command.extend(["--branch", branch])
    command.extend([url, destination])

    with git_auth_environment() as env:
        # stderr/stdout are returned to the caller, but callers must redact credentials before logging.
        return subprocess.run(command, capture_output=True, text=True, env=env, check=False)
