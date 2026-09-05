import asyncio
from typing import Any
from core.runtime.permissions import get_workspace_root, validate_terminal_command


async def execute_command(command: str, timeout: float = 30.0) -> dict[str, Any]:
    """Execute shell command inside workspace with timeout, output capture, and safety checks."""
    validate_terminal_command(command)
    workspace = get_workspace_root()

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace),
    )

    try:
        stdout_data, stderr_data = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:
            pass
        raise TimeoutError(f"Command execution timed out after {timeout} seconds.")

    stdout = stdout_data.decode("utf-8", errors="replace")
    stderr = stderr_data.decode("utf-8", errors="replace")

    max_len = 10000
    if len(stdout) > max_len:
        stdout = stdout[:max_len] + "\n[STDOUT TRUNCATED]"
    if len(stderr) > max_len:
        stderr = stderr[:max_len] + "\n[STDERR TRUNCATED]"

    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
