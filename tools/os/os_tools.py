"""Safe operating-system inspection tools for FRIDAY.

These tools intentionally inspect the machine without exposing environment
variables, credentials, or arbitrary command execution. Existing
terminal.execute remains the explicit command execution capability.
"""

from __future__ import annotations

import getpass
import os
import platform
from typing import Any

import psutil
from langchain.tools import tool


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
    usage = psutil.disk_usage(os.path.abspath(path))
    return {
        "path": os.path.abspath(path),
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "free_gb": round(usage.free / (1024**3), 2),
        "percent": usage.percent,
    }


async def os_current_directory() -> dict[str, str]:
    """Return the current FRIDAY process working directory."""
    return {"working_directory": os.getcwd()}


os_system_info_tool = tool("os_system_info")(os_system_info)
os_list_processes_tool = tool("os_list_processes")(os_list_processes)
os_disk_usage_tool = tool("os_disk_usage")(os_disk_usage)
os_current_directory_tool = tool("os_current_directory")(os_current_directory)

OS_LANGCHAIN_TOOLS = [
    os_system_info_tool,
    os_list_processes_tool,
    os_disk_usage_tool,
    os_current_directory_tool,
]
