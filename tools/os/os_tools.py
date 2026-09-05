"""Operating-system and machine filesystem tools for FRIDAY.

OS filesystem tools intentionally work outside the configured project workspace so
FRIDAY can inspect and modify files/folders across mounted drives. Credentials,
private keys, and other sensitive paths remain blocked by the central permission
validator. Write/mutation tools are marked PERMISSION_REQUIRED in the registry.
"""

from __future__ import annotations

import asyncio
import getpass
import os
import platform
import shutil
from pathlib import Path
from typing import Any

import psutil
from langchain.tools import tool

from core.runtime.permissions import validate_workspace_path


async def os_system_info() -> dict[str, Any]:
    """Return safe host, OS, Python, CPU, memory, and current-user information."""
    memory = psutil.virtual_memory()
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "username": getpass.getuser(),
        "cpu_count": psutil.cpu_count(logical=True),
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "memory_available_gb": round(memory.available / (1024**3), 2),
        "memory_percent": memory.percent,
        "working_directory": os.getcwd(),
    }


async def os_list_processes(limit: int = 20) -> list[dict[str, Any]]:
    """Return a bounded list of running processes without command-line arguments or secrets."""
    limit = max(1, min(limit, 100))
    processes: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "username", "status", "cpu_percent", "memory_percent"]):
        try:
            info = process.info
            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "username": info.get("username"),
                    "status": info.get("status"),
                    "cpu_percent": info.get("cpu_percent"),
                    "memory_percent": round(float(info.get("memory_percent") or 0), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda item: (item["cpu_percent"] or 0), reverse=True)
    return processes[:limit]


async def os_disk_usage(path: str = ".") -> dict[str, Any]:
    """Return disk capacity and usage for a local path."""
    target = Path(path).expanduser().resolve()
    usage = psutil.disk_usage(str(target))
    return {
        "path": str(target),
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "percent": usage.percent,
    }


async def os_list_drives() -> list[dict[str, Any]]:
    """List mounted drives/partitions available to the FRIDAY process."""
    def collect() -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for partition in psutil.disk_partitions(all=False):
            item: dict[str, Any] = {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "filesystem": partition.fstype,
                "options": partition.opts,
            }
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                item.update(
                    {
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    }
                )
            except (OSError, PermissionError):
                pass
            results.append(item)
        return results

    return await asyncio.to_thread(collect)


async def os_read_file(path: str) -> str:
    """Read a text file from any accessible local drive/path."""
    target = validate_workspace_path(path, allow_outside=True)

    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not target.is_file():
        raise ValueError(f"Path is not a file: {path}")

    def read() -> str:
        with target.open("rb") as handle:
            sample = handle.read(1024)
            if b"\x00" in sample:
                raise ValueError(f"File appears to be binary: {path}")
        content = target.read_text(encoding="utf-8", errors="replace")
        max_chars = 100_000
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[OUTPUT TRUNCATED - MAX {max_chars} CHARACTERS]"
        return content

    return await asyncio.to_thread(read)


async def os_write_file(path: str, content: str, overwrite: bool = True) -> str:
    """Write a UTF-8 text file to any accessible local drive/path."""
    target = validate_workspace_path(path, allow_outside=True)

    if target.exists() and target.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: {path}")
    if target.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {path}")

    def write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    await asyncio.to_thread(write)
    return f"Successfully wrote {len(content)} characters to {target}"


async def os_list_directory(path: str = ".", include_hidden: bool = False) -> list[dict[str, Any]]:
    """List files and folders from any accessible local drive/path."""
    target = validate_workspace_path(path, allow_outside=True)
    if not target.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    def collect() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in target.iterdir():
            if not include_hidden and item.name.startswith("."):
                continue
            try:
                stat = item.stat()
                items.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": stat.st_mtime,
                    }
                )
            except (OSError, PermissionError):
                continue
        return sorted(items, key=lambda item: (item["type"] != "directory", item["name"].lower()))

    return await asyncio.to_thread(collect)


async def os_create_directory(path: str) -> str:
    """Create a directory and its missing parents on any accessible local drive."""
    target = validate_workspace_path(path, allow_outside=True)
    if target.exists():
        if target.is_dir():
            return f"Directory already exists: {target}"
        raise FileExistsError(f"A file already exists at: {target}")

    await asyncio.to_thread(target.mkdir, parents=True, exist_ok=False)
    return f"Successfully created directory: {target}"


async def os_path_exists(path: str) -> dict[str, Any]:
    """Check whether a file or directory exists anywhere on an accessible drive."""
    target = validate_workspace_path(path, allow_outside=True)
    exists = await asyncio.to_thread(target.exists)
    return {
        "path": str(target),
        "exists": exists,
        "type": "directory" if exists and target.is_dir() else "file" if exists else None,
    }


async def os_delete_path(path: str, recursive: bool = False) -> str:
    """Delete a file or directory after permission validation."""
    target = validate_workspace_path(path, allow_outside=True)
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    def delete() -> None:
        if target.is_dir():
            if not recursive:
                target.rmdir()
            else:
                shutil.rmtree(target)
        else:
            target.unlink()

    await asyncio.to_thread(delete)
    return f"Successfully deleted: {target}"


os_system_info_tool = tool(os_system_info, name="os_system_info")
os_list_processes_tool = tool(os_list_processes, name="os_list_processes")
os_disk_usage_tool = tool(os_disk_usage, name="os_disk_usage")
os_list_drives_tool = tool(os_list_drives, name="os_list_drives")
os_read_file_tool = tool(os_read_file, name="os_read_file")
os_write_file_tool = tool(os_write_file, name="os_write_file")
os_list_directory_tool = tool(os_list_directory, name="os_list_directory")
os_create_directory_tool = tool(os_create_directory, name="os_create_directory")
os_path_exists_tool = tool(os_path_exists, name="os_path_exists")
os_delete_path_tool = tool(os_delete_path, name="os_delete_path")

OS_LANGCHAIN_TOOLS = [
    os_system_info_tool,
    os_list_processes_tool,
    os_disk_usage_tool,
    os_list_drives_tool,
    os_read_file_tool,
    os_write_file_tool,
    os_list_directory_tool,
    os_create_directory_tool,
    os_path_exists_tool,
    os_delete_path_tool,
]
