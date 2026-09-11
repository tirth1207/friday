"""Git tools used by the Developer Agent."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

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
    return await run_git(["status", "--short"])


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
    await run_git(["add", "--", *cleaned])
    return json_result({"success": True, "staged": cleaned})


async def git_commit(message: str) -> dict[str, Any]:
    """Create a commit and return concrete commit evidence."""
    message = str(message).strip()
    if not message:
        raise ValueError("Commit message is required")
    if len(message) > 200:
        raise ValueError("Commit message is too long")

    status = await run_git(["status", "--short"])
    if not status.strip():
        return {"success": False, "committed": False, "reason": "No staged or unstaged changes were present."}

    output = await run_git(["commit", "-m", message])
    commit_sha = (await run_git(["rev-parse", "HEAD"])).strip()
    return {
        "success": True,
        "committed": True,
        "commit_sha": commit_sha,
        "message": message,
        "output": output.strip(),
    }


async def git_push(remote: str = "origin", branch: str | None = None) -> dict[str, Any]:
    """Push and verify that the remote branch points at the local HEAD."""
    remote = str(remote).strip()
    if not remote or remote.startswith("-"):
        raise ValueError("A valid Git remote is required")

    current_branch = (await run_git(["branch", "--show-current"])).strip()
    target_branch = str(branch).strip() if branch is not None and str(branch).strip() else current_branch
    if not target_branch or target_branch.startswith("-") or ".." in target_branch:
        raise ValueError("Invalid Git branch name")

    push_args = ["push", remote, f"HEAD:{target_branch}"]
    output = await run_git(push_args)
    local_sha = (await run_git(["rev-parse", "HEAD"])).strip()
    remote_sha = (await run_git(["ls-remote", remote, f"refs/heads/{target_branch}"])).strip()
    remote_head = remote_sha.split()[0] if remote_sha else ""

    if not remote_head or remote_head != local_sha:
        raise RuntimeError(
            f"Git push returned successfully but remote verification failed: expected {local_sha}, got {remote_head or 'no remote SHA'}."
        )

    return {
        "success": True,
        "pushed": True,
        "remote": remote,
        "branch": target_branch,
        "commit_sha": local_sha,
        "remote_sha": remote_head,
        "output": output.strip(),
    }


def json_result(value: dict[str, Any]) -> dict[str, Any]:
    """Keep the tiny helper explicit for tool-result serialization compatibility."""
    return value
