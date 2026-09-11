"""Cross-platform terminal execution for the Developer Agent."""
from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

from core.runtime.permissions import get_workspace_root, validate_terminal_command


_MAX_OUTPUT = 10000
_DEFAULT_TIMEOUT = 30.0
_MAX_TIMEOUT = 300.0


def _run_shell_command(command: str, workspace: str, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run a shell command synchronously; called from a worker thread."""
    return subprocess.run(
        command,
        shell=True,
        cwd=workspace,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


async def execute_command(command: str, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Execute a shell command inside the workspace with timeout and output capture.

    Uses subprocess.run in a worker thread rather than asyncio.create_subprocess_shell.
    This avoids the Windows event-loop subprocess backend failure that previously made
    the Developer Agent's terminal unusable.
    """
    command = str(command).strip()
    if not command:
        raise ValueError("Terminal command is required")
    validate_terminal_command(command)
    workspace = get_workspace_root()
    if not workspace.exists() or not workspace.is_dir():
        raise RuntimeError(f"Terminal workspace does not exist: {workspace}")

    try:
        result = await asyncio.to_thread(
            _run_shell_command,
            command,
            str(workspace),
            min(max(float(timeout), 0.1), _MAX_TIMEOUT),
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"Command execution timed out after {min(max(float(timeout), 0.1), _MAX_TIMEOUT)} seconds."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to start terminal command: {exc}") from exc

    stdout = result.stdout[-_MAX_OUTPUT:] if len(result.stdout) > _MAX_OUTPUT else result.stdout
    stderr = result.stderr[-_MAX_OUTPUT:] if len(result.stderr) > _MAX_OUTPUT else result.stderr
    if len(result.stdout) > _MAX_OUTPUT:
        stdout = "[STDOUT TRUNCATED]\n" + stdout
    if len(result.stderr) > _MAX_OUTPUT:
        stderr = "[STDERR TRUNCATED]\n" + stderr

    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
