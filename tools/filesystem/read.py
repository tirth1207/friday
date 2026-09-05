from core.runtime.permissions import validate_workspace_path


async def read_file(path: str) -> str:
    """Read file content safely within allowed workspace limits."""
    target_path = validate_workspace_path(path)

    if not target_path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    if not target_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    # Binary check
    try:
        with open(target_path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                raise ValueError(f"File appears to be binary: {path}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise IOError(f"Could not read file: {e}")

    content = target_path.read_text(encoding="utf-8", errors="replace")

    max_chars = 50000
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n[OUTPUT TRUNCATED - MAX {max_chars} CHARACTERS Exceeded]"

    return content
