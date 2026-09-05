from pathlib import Path


async def read_file(
    file_path: str,
):

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File does not exist: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # Prevent enormous outputs.
    max_chars = 30000

    if len(content) > max_chars:

        content = (
            content[:max_chars]
            + "\n\n[OUTPUT TRUNCATED]"
        )

    return content