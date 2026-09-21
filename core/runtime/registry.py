from typing import Any, Callable, Coroutine
from pydantic import BaseModel, Field

from core.runtime.permissions import PermissionLevel


class ToolMetadata(BaseModel):
    name: str
    description: str
    permission: PermissionLevel = PermissionLevel.SAFE
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        description: str,
        permission: PermissionLevel = PermissionLevel.SAFE,
        parameters: dict[str, Any] | None = None,
    ):
        """Register a tool with metadata and its execution function."""
        self._tools[name] = func
        self._metadata[name] = ToolMetadata(
            name=name,
            description=description,
            permission=permission,
            parameters=parameters or {},
        )

    @staticmethod
    def canonical_name(name: str) -> str:
        """Normalize provider-safe tool names back to FRIDAY's canonical dotted ID."""
        value = str(name or "").strip()
        if "__" in value and "." not in value:
            value = value.replace("__", ".")
        return value

    def resolve_name(self, name: str) -> str | None:
        """Resolve a canonical or provider-safe tool name to a registered tool ID."""
        canonical = self.canonical_name(name)
        if canonical in self._tools:
            return canonical
        return None

    def get_tool(self, name: str) -> Callable[..., Coroutine[Any, Any, Any]] | None:
        canonical = self.resolve_name(name)
        return self._tools.get(canonical) if canonical else None

    def get_metadata(self, name: str) -> ToolMetadata | None:
        canonical = self.resolve_name(name)
        return self._metadata.get(canonical) if canonical else None

    def list_tools(self) -> list[dict[str, Any]]:
        return [meta.model_dump() for meta in self._metadata.values()]


tool_registry = ToolRegistry()
