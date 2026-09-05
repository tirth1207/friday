from pathlib import Path


async def list_directory(
    directory: str,
):

    path = Path(directory)

    if not path.exists():
        raise FileNotFoundError(
            f"Directory does not exist: {directory}"
        )

    if not path.is_dir():
        raise NotADirectoryError(
            f"Not a directory: {directory}"
        )

    items = []

    for item in path.iterdir():

        items.append({
            "name": item.name,
            "type": (
                "directory"
                if item.is_dir()
                else "file"
            ),
        })

    return items