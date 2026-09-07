import asyncio
from core.runtime.permissions import get_workspace_root


async def run_git(args: list[str]) -> str:
    workspace = get_workspace_root()
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace),
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"Git command 'git {' '.join(args)}' failed: {err}")
    return stdout.decode("utf-8", errors="replace")


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
