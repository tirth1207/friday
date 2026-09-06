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
    ) -> Any:
        tool_func = tool_registry.get_tool(tool_name)
        tool_meta = tool_registry.get_metadata(tool_name)

        if not tool_func or not tool_meta:
            error_msg = f"Unknown tool requested: '{tool_name}'"
            await agent_runtime.tool_error(
                agent=agent,
                tool=tool_name,
                description=error_msg,
                metadata={"error": error_msg},
            )
            raise ValueError(error_msg)

        required_permission = tool_meta.permission
        if tool_name == "github.api" and str(arguments.get("method", "GET")).upper() == "GET":
            required_permission = PermissionLevel.SAFE

        if required_permission == PermissionLevel.BLOCKED:
            error_msg = f"Tool '{tool_name}' execution is blocked by policy."
            await agent_runtime.tool_error(
                agent=agent,
                tool=tool_name,
                description=error_msg,
                metadata={"error": error_msg},
            )
            raise PermissionError(error_msg)

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
                result = await tool_func(**arguments)

            safe_metadata: dict[str, Any] = {}
            if isinstance(result, list):
                safe_metadata = {
                    "count": len(result),
                    "results": result[:20],
                }
            elif isinstance(result, str):
                safe_metadata = {
                    "length": len(result),
                    "preview": result[:500],
                }
            elif isinstance(result, dict):
                safe_metadata = {
                    k: (v if not isinstance(v, (str, list, dict)) else str(v)[:200])
                    for k, v in result.items()
                }
            else:
                safe_metadata = {"result": str(result)[:500]}

            await agent_runtime.complete_tool(
                agent=agent,
                tool=tool_name,
                description="Tool execution completed successfully.",
                metadata=safe_metadata,
            )

            return result

        except Exception as error:
            error_text = str(error)
            await agent_runtime.tool_error(
                agent=agent,
                tool=tool_name,
                description=error_text,
                metadata={"error": error_text[:500]},
            )
            raise


tool_executor = ToolExecutor()
