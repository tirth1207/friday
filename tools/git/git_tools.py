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
