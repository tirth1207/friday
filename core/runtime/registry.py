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

    def get_tool(self, name: str) -> Callable[..., Coroutine[Any, Any, Any]] | None:
        return self._tools.get(name)

    def get_metadata(self, name: str) -> ToolMetadata | None:
        return self._metadata.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [meta.model_dump() for meta in self._metadata.values()]


tool_registry = ToolRegistry()
