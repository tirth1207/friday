"""Git tools used by the Developer Agent."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from core.github_oauth import load_connection, refresh_connection_if_needed
from core.runtime.permissions import get_workspace_root


def _git_env() -> dict[str, str]:
    """Build a non-interactive Git environment with ephemeral GitHub auth."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    token = str((load_connection() or {}).get("access_token") or "").strip()
    if token:
        env["GIT_ASKPASS"] = str(Path(__file__).resolve().parents[2] / "core" / "runtime" / "github_askpass.py")
        env["FRIDAY_GITHUB_TOKEN"] = token
    return env


def _run_git_sync(args: list[str], workspace: Path) -> subprocess.CompletedProcess[str]:
    """Run Git without asyncio subprocess APIs for Windows compatibility."""
    return subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        env=_git_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


async def run_git(args: list[str]) -> str:
    """Run a Git command in the active workspace with structured failures."""
    if not args:
        raise ValueError("Git command arguments are required")
    workspace = Path(get_workspace_root()).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise RuntimeError(f"Git workspace does not exist: {workspace}")

    await refresh_connection_if_needed()
    try:
        result = await asyncio.to_thread(_run_git_sync, args, workspace)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Git command 'git {' '.join(args)}' timed out after 120 seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to start Git: {exc}") from exc

    stdout = result.stdout
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"Git command 'git {' '.join(args)}' failed with exit code {result.returncode}: {stderr}"
        )
    return stdout


async def git_status() -> str:
    return await run_git(["status"])


async def git_diff() -> str:
    return await run_git(["diff"])


async def git_log(max_count: int = 10) -> str:
    return await run_git(["log", f"-n{max_count}", "--oneline"])


async def git_branch() -> str:
    return await run_git(["branch", "-a"])


async def git_add(paths: list[str]) -> str:
    """Stage explicit repository paths; the executor supplies the permission boundary."""
    if not paths:
        raise ValueError("At least one path is required for git.add")
    cleaned = [str(path).strip() for path in paths if str(path).strip()]
    if not cleaned:
        raise ValueError("At least one non-empty path is required for git.add")
    if any(path.startswith("-") for path in cleaned):
        raise ValueError("Git paths may not begin with '-'")
    return await run_git(["add", "--", *cleaned])


async def git_commit(message: str) -> str:
    """Create a commit from the already-staged changes."""
    message = str(message).strip()
    if not message:
        raise ValueError("Commit message is required")
    if len(message) > 200:
        raise ValueError("Commit message is too long")
    return await run_git(["commit", "-m", message])


async def git_push(remote: str = "origin", branch: str | None = None) -> str:
    """Push the current or explicitly named branch to a configured remote."""
    remote = str(remote).strip()
    if not remote or remote.startswith("-"):
        raise ValueError("A valid Git remote is required")
    if branch is None or not str(branch).strip():
        return await run_git(["push", remote])
    branch = str(branch).strip()
    if branch.startswith("-") or ".." in branch:
        raise ValueError("Invalid Git branch name")
    return await run_git(["push", remote, f"HEAD:{branch}"])
