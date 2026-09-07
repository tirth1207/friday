"""Safe capability discovery for FRIDAY's tool-aware coordinator."""

from __future__ import annotations

from typing import Any

from core.runtime.registry import tool_registry


_CAPABILITY_GROUPS: dict[str, tuple[str, ...]] = {
    "intelligence": ("osiris.", "github."),
    "computer": ("os.", "filesystem.", "terminal."),
    "engineering": ("git.", "developer."),
    "cognition": ("cognition.", "self.", "agent."),
}


def list_capabilities(include_permission_required: bool = True) -> list[dict[str, Any]]:
    """Return registered capabilities grouped by safe, discoverable prefixes."""
    tools = tool_registry.list_tools()
    capabilities: list[dict[str, Any]] = []
    for group, prefixes in _CAPABILITY_GROUPS.items():
        names = [
            tool["name"]
            for tool in tools
            if any(tool["name"].startswith(prefix) for prefix in prefixes)
            and (include_permission_required or tool.get("permission") == "SAFE")
        ]
        if names:
            capabilities.append({"group": group, "tools": sorted(names)})
    return capabilities


def capability_catalog() -> dict[str, list[str]]:
    """Return a compact group-to-tool catalog for planning and diagnostics."""
    return {item["group"]: item["tools"] for item in list_capabilities()}
