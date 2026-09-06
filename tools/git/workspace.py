"""Prepare isolated local workspaces for selected GitHub repositories."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from core.config import settings
from core.runtime.permissions import get_workspace_root

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


async def prepare_repository_workspace(repository: str, ref: str | None = None) -> dict[str, Any]:
    """Clone or reuse a selected GitHub repository in FRIDAY's isolated workspace."""
    if not _REPOSITORY.fullmatch(repository.strip()):
        raise ValueError("Repository must use owner/name format.")

    repo = repository.strip()
    workspace_root = Path(settings.friday_workspace).resolve()
    workspace_dir = workspace_root / ".friday" / "workspaces"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    key = hashlib.sha256(f"{repo}\0{ref or ''}".encode()).hexdigest()[:16]
    target = workspace_dir / key
    git_dir = target / ".git"

    if git_dir.is_dir():
        return {"repository": repo, "ref": ref, "workspace": str(target), "reused": True}

    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise RuntimeError(f"Execution workspace is not empty: {target}")

    clone_url = f"https://github.com/{repo}.git"
    command = ["git", "clone", "--depth", "1"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([clone_url, str(target)])

    env = os.environ.copy()
    # Keep credentials out of argv and command/event logs. Git reads this header from its environment config.
    try:
        from tools.github.repository_agent import settings as github_settings
        token = str(github_settings.pat or "").strip()
    except Exception:
        token = ""
    if token:
        env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: bearer {token}",
        })

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        try:
            target.rmdir()
        except OSError:
            pass
        error = stderr.decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"Could not prepare repository workspace: {error}")

    return {
        "repository": repo,
        "ref": ref,
        "workspace": str(target),
        "reused": False,
        "output": stdout.decode("utf-8", errors="replace")[-1000:],
    }
