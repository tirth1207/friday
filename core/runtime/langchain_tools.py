"""Bridge FRIDAY's tool registry to native LangChain tool calling."""

from __future__ import annotations

import inspect
import re
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from core.runtime.registry import tool_registry


_ALLOWED_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def _model_tool_name(registry_name: str) -> str:
    """Convert FRIDAY's dotted internal name into a provider-safe tool name."""
    if _ALLOWED_NAME.fullmatch(registry_name):
        return registry_name
    return registry_name.replace(".", "__")


def get_langchain_tools() -> list[BaseTool]:
    """Expose registered FRIDAY tools as provider-compatible LangChain tools."""
    tools: list[BaseTool] = []

    for metadata in tool_registry.list_tools():
        registry_name = metadata["name"]
        func = tool_registry.get_tool(registry_name)
        if func is None:
            continue

        model_name = _model_tool_name(registry_name)
        description = metadata["description"]

        if isinstance(func, BaseTool):
            if func.name == model_name:
                tool = func
            elif getattr(func, "coroutine", None) is not None:
                tool = StructuredTool.from_function(
                    coroutine=func.coroutine,
                    name=model_name,
                    description=description,
                    args_schema=func.args_schema,
                )
            else:
                tool = StructuredTool.from_function(
                    func=func.invoke,
                    name=model_name,
                    description=description,
                    args_schema=func.args_schema,
                )
            tools.append(tool)
            continue

        if not callable(func):
            continue

        if inspect.iscoroutinefunction(func):
            tool = StructuredTool.from_function(
                coroutine=func,
                name=model_name,
                description=description,
            )
        else:
            tool = StructuredTool.from_function(
                func=func,
                name=model_name,
                description=description,
            )
        tools.append(tool)

    return tools


def registry_tool_name(model_name: str) -> str:
    """Map a provider-safe model name back to FRIDAY's registry name."""
    return model_name.replace("__", ".")


def tool_names() -> list[str]:
    """Return the internal FRIDAY tool names exposed to the bridge."""
    return [metadata["name"] for metadata in tool_registry.list_tools()]


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
