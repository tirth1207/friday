import re
from enum import Enum
from pathlib import Path

from core.config import settings


class PermissionLevel(str, Enum):
    SAFE = "safe"
    PERMISSION_REQUIRED = "permission_required"
    BLOCKED = "blocked"


# Files/folders that should never be accessed or modified by default
SENSITIVE_PATTERNS = [
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".git/config",
]

# Dangerous terminal command patterns that must be blocked or require confirmation
BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/s\b",
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\breg\s+delete\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]


def get_workspace_root() -> Path:
    """Return the absolute, resolved workspace path."""
    return Path(settings.friday_workspace).resolve()


def validate_workspace_path(path_str: str, allow_outside: bool = False) -> Path:
    """
    Validate that path_str resolves to a path inside the configured workspace root.
    Prevents path traversal attacks (e.g., ../../etc/passwd).
    Throws PermissionError if unsafe.
    """
    workspace = get_workspace_root()

    raw_path = Path(path_str)
    if not raw_path.is_absolute():
        target_path = (workspace / raw_path).resolve()
    else:
        target_path = raw_path.resolve()

    target_str = str(target_path)
    target_parts = [p.lower() for p in target_path.parts]

    for sensitive in SENSITIVE_PATTERNS:
        sens_lower = sensitive.lower()
        if sens_lower in target_parts or target_str.lower().endswith(sens_lower):
            raise PermissionError(f"Access to sensitive file or path is restricted: {path_str}")

    if not allow_outside:
        try:
            target_path.relative_to(workspace)
        except ValueError:
            raise PermissionError(f"Path is outside allowed workspace ({workspace}): {path_str}")

    return target_path


def validate_terminal_command(command: str) -> None:
    """
    Validate a terminal command string. Block destructive/dangerous commands.
    """
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise PermissionError(f"Dangerous or destructive command blocked: {command}")
