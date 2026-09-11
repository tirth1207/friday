"""Prepare isolated local workspaces for selected GitHub repositories."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.config import settings
from core.github_oauth import load_connection, refresh_connection_if_needed

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _remove_failed_target(target: Path) -> None:
    """Remove only the task-specific clone directory after a failed clone."""
    try:
        if target.is_dir():
            shutil.rmtree(target)
    except OSError:
        pass


def _run_process(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    """Run a process in a worker thread instead of asyncio subprocess APIs.

    asyncio.create_subprocess_* is unreliable in some Windows event-loop/runtime
    combinations used by FRIDAY. subprocess.run is synchronous but is safely
    isolated from the event loop with asyncio.to_thread.
    """
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


async def prepare_repository_workspace(repository: str, ref: str | None = None) -> dict[str, Any]:
    """Clone or reuse a selected GitHub repository in FRIDAY's isolated workspace."""
    if not _REPOSITORY.fullmatch(repository.strip()):
        raise ValueError("Repository must use owner/name format.")

    await refresh_connection_if_needed()
    repo = repository.strip()
    workspace_root = Path(settings.friday_workspace).resolve()
    workspace_dir = workspace_root / ".friday" / "workspaces"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    key = hashlib.sha256(f"{repo}\0{ref or ''}".encode()).hexdigest()[:16]
    target = workspace_dir / key
    git_dir = target / ".git"

    if git_dir.is_dir():
        return {"repository": repo, "ref": ref, "workspace": str(target), "reused": True}

    if target.exists():
        _remove_failed_target(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    clone_url = f"https://github.com/{repo}.git"
    command = ["git", "clone", "--depth", "1"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([clone_url, str(target)])

    env = os.environ.copy()
    token = str((load_connection() or {}).get("access_token") or "").strip()
    if token:
        env["GIT_ASKPASS"] = str(Path(__file__).resolve().parents[2] / "core" / "runtime" / "github_askpass.py")
        env["FRIDAY_GITHUB_TOKEN"] = token
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        result = await asyncio.to_thread(_run_process, command, env=env, timeout=120.0)
    except subprocess.TimeoutExpired as exc:
        _remove_failed_target(target)
        raise TimeoutError("Repository clone timed out after 120 seconds.") from exc
    except OSError as exc:
        _remove_failed_target(target)
        raise RuntimeError(f"Unable to start Git: {exc}") from exc

    if result.returncode != 0:
        _remove_failed_target(target)
        error = result.stderr[-4000:]
        raise RuntimeError(f"Could not prepare repository workspace (git clone exited {result.returncode}): {error}")

    return {
        "repository": repo,
        "ref": ref,
        "workspace": str(target),
        "reused": False,
        "output": result.stdout[-1000:],
    }
