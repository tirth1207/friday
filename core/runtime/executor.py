from inspect import isawaitable
import hashlib
import json
import time
from typing import Any

from core.agents.runtime import agent_runtime
from core.runtime.permissions import PermissionLevel
from core.runtime.registry import tool_registry


class ToolExecutor:
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        agent: str = "Developer Agent",
        confirmed: bool = False,
    ) -> Any:
        tool_func = tool_registry.get_tool(tool_name)
        tool_meta = tool_registry.get_metadata(tool_name)

        if not tool_func or not tool_meta:
            error_msg = f"Unknown tool requested: '{tool_name}'"
            await agent_runtime.tool_error(agent=agent, tool=tool_name, description=error_msg, metadata={"error": error_msg})
            raise ValueError(error_msg)

        required_permission = tool_meta.permission
        if tool_name == "github.api" and str(arguments.get("method", "GET")).upper() == "GET":
            required_permission = PermissionLevel.SAFE

        if required_permission == PermissionLevel.BLOCKED:
            error_msg = f"Tool '{tool_name}' execution is blocked by policy."
            await agent_runtime.tool_error(agent=agent, tool=tool_name, description=error_msg, metadata={"error": error_msg})
            raise PermissionError(error_msg)

        if required_permission == PermissionLevel.PERMISSION_REQUIRED and not confirmed:
            error_msg = f"Tool '{tool_name}' requires explicit confirmation before execution. Pass confirmed=True after the user approves the operation."
            await agent_runtime.tool_error(agent=agent, tool=tool_name, description=error_msg, metadata={"error": error_msg, "requires_confirmation": True})
            raise PermissionError(error_msg)

        cacheable = required_permission == PermissionLevel.SAFE
        if cacheable:
            cached = _read_only_cache.get(tool_name, arguments)
            if cached is not None:
                await agent_runtime.complete_tool(
                    agent=agent,
                    tool=tool_name,
                    description="Reused identical recent read-only result.",
                    metadata={"cached": True},
                )
                return cached

        await agent_runtime.start_tool(
            agent=agent,
            tool=tool_name,
            description=f"Executing {tool_name}",
            metadata={"arguments": {k: str(v)[:100] for k, v in arguments.items()}},
        )

        try:
            if hasattr(tool_func, "ainvoke"):
                result = await tool_func.ainvoke(arguments)
            else:
                result = tool_func(**arguments)
                if isawaitable(result):
                    result = await result

            if isinstance(result, list):
                safe_metadata = {"count": len(result), "results": result[:20]}
            elif isinstance(result, str):
                safe_metadata = {"length": len(result), "preview": result[:500]}
            elif isinstance(result, dict):
                safe_metadata = {k: (v if not isinstance(v, (str, list, dict)) else str(v)[:200]) for k, v in result.items()}
            else:
                safe_metadata = {"result": str(result)[:500]}

            await agent_runtime.complete_tool(
                agent=agent,
                tool=tool_name,
                description="Tool execution completed successfully.",
                metadata=safe_metadata,
            )
            if cacheable:
                _read_only_cache.put(tool_name, arguments, result)
            return result
        except Exception as error:
            error_text = str(error)
            await agent_runtime.tool_error(agent=agent, tool=tool_name, description=error_text, metadata={"error": error_text[:500]})
            raise


class _ReadOnlyToolCache:
    """Short-lived request-process cache for identical safe tool calls.

    This prevents duplicate read-only calls (for example two identical web
    searches) from being executed back-to-back by the planner/model.
    """

    def __init__(self, ttl_seconds: float = 30.0):
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def _key(self, tool_name: str, arguments: dict[str, Any]) -> str:
        payload = json.dumps(
            {"tool": tool_name, "arguments": arguments},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        key = self._key(tool_name, arguments)
        entry = self._entries.get(key)
        if not entry:
            return None
        created, result = entry
        if time.monotonic() - created > self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return result

    def put(self, tool_name: str, arguments: dict[str, Any], result: Any) -> None:
        self._entries[self._key(tool_name, arguments)] = (time.monotonic(), result)


_read_only_cache = _ReadOnlyToolCache()


tool_executor = ToolExecutor()
