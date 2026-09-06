"""Bridge FRIDAY's tool registry to native LangChain tool calling."""

from __future__ import annotations

import inspect
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from core.runtime.registry import tool_registry


def get_langchain_tools() -> list[BaseTool]:
    """Expose every registered FRIDAY tool as a real LangChain tool schema."""
    tools: list[BaseTool] = []

    for metadata in tool_registry.list_tools():
        name = metadata["name"]
        func = tool_registry.get_tool(name)
        if func is None:
            continue

        if isinstance(func, BaseTool):
            tool = func
            if tool.name != name:
                tool = StructuredTool.from_function(
                    coroutine=tool.coroutine,
                    name=name,
                    description=metadata["description"],
                )
            tools.append(tool)
            continue

        if not callable(func):
            continue

        if inspect.iscoroutinefunction(func):
            tool = StructuredTool.from_function(
                coroutine=func,
                name=name,
                description=metadata["description"],
            )
        else:
            tool = StructuredTool.from_function(
                func=func,
                name=name,
                description=metadata["description"],
            )
        tools.append(tool)

    return tools


def tool_names() -> list[str]:
    """Return the names exposed to the model."""
    return [tool.name for tool in get_langchain_tools()]


def serialize_tool_result(result: Any, max_chars: int = 80_000) -> str:
    """Serialize a tool result safely for a LangChain ToolMessage."""
    import json

    try:
        text = json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        text = str(result)

    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[TOOL RESULT TRUNCATED]"
