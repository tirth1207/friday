from pathlib import Path


async def search_files(
    directory: str,
    query: str,
):

    root = Path(directory)

    if not root.exists():
        raise FileNotFoundError(
            f"Directory does not exist: {directory}"
        )

    results = []

    query_lower = query.lower()

    ignored = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".next",
        "dist",
        "build",
    }

    for path in root.rglob("*"):

        if any(
            part in ignored
            for part in path.parts
        ):
            continue

        if not path.is_file():
            continue

        if query_lower in path.name.lower():

            results.append(
                str(path)
            )

    return results[:100]