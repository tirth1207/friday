import re
from enum import Enum
from pathlib import Path

from core.config import settings
from core.runtime.workspace import get_scoped_workspace


class PermissionLevel(str, Enum):
    SAFE = "safe"
    PERMISSION_REQUIRED = "permission_required"
    BLOCKED = "blocked"


SENSITIVE_PATTERNS = [
    ".env", ".env.local", "id_rsa", "id_ed25519", ".pem", ".key", ".git/config",
]

# FRIDAY-owned metadata must never be treated as the user's repository root.
# Developer filesystem mutations should target the cloned repository itself;
# internal runtime state belongs in this directory and is not a valid target
# for normal repository edits.
INTERNAL_WORKSPACE_DIRS = {".friday"}

BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b", r"\bdel\s+/s\b", r"\bformat\b", r"\bdiskpart\b",
    r"\breg\s+delete\b", r"\bshutdown\b", r"\breboot\b", r"\bmkfs\b", r"\bdd\s+if=",
]


def get_workspace_root() -> Path:
    """Return the active task workspace, falling back to FRIDAY's root."""
    scoped = get_scoped_workspace()
    if scoped is not None:
        return scoped
    return Path(settings.friday_workspace).resolve()


def validate_workspace_path(path_str: str, allow_outside: bool = False) -> Path:
    """Validate that path_str resolves inside the active workspace.

    Normal filesystem operations cannot write FRIDAY's internal metadata
    directory. A repository-relative path such as ``test.txt`` therefore
    resolves to the repository root, while ``.friday/test.txt`` is rejected.
    """
    workspace = get_workspace_root()
    raw_path = Path(path_str)
    target_path = (workspace / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
    target_str = str(target_path)
    target_parts = [p.lower() for p in target_path.parts]
    workspace_parts = len(workspace.parts)

    for sensitive in SENSITIVE_PATTERNS:
        sens_lower = sensitive.lower()
        if sens_lower in target_parts or target_str.lower().endswith(sens_lower):
            raise PermissionError(f"Access to sensitive file or path is restricted: {path_str}")

    if not allow_outside:
        try:
            relative = target_path.relative_to(workspace)
        except ValueError:
            raise PermissionError(f"Path is outside allowed workspace ({workspace}): {path_str}")

        relative_parts = [part.lower() for part in relative.parts]
        if relative_parts and relative_parts[0] in INTERNAL_WORKSPACE_DIRS:
            raise PermissionError(
                f"FRIDAY internal path is not a valid repository edit target: {path_str}. "
                "Use a path relative to the repository root instead."
            )

    return target_path


def validate_terminal_command(command: str) -> None:
    """Validate a terminal command string. Block destructive/dangerous commands."""
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise PermissionError(f"Dangerous or destructive command blocked: {command}")
