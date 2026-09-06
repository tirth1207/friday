"""Native LangChain tool-calling orchestrator for FRIDAY."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import tools
from core.agents.runtime import agent_runtime
from core.agents.specialized import GitHubAgent, OSAgent, ResearchAgent
from core.memory import memory_store
from core.memory.context import resolve_request
from core.orchestrator import (
    _execute_github_tool,
    _format_env_key_result,
    _format_repository_list,
    _is_environment_key_request,
    _is_github_repository_list_request,
    answer_conversationally,
    is_tool_required,
)
from core.runtime.executor import tool_executor
from core.runtime.langchain_tools import get_langchain_tools, serialize_tool_result
from providers.nvidia.client import get_model


SYSTEM_PROMPT = """
You are FRIDAY, a personal AI operating assistant and senior software-engineering agent.
You have native structured tool calling. Use tools whenever the user asks about a real
repository, local machine, files, Git, GitHub, code, or another tool-backed capability.
Never invent tool names or tool arguments. Use the schemas supplied by LangChain.

Repository rules:
- A named repository is always more specific than a request to list repositories.
- For a repository explanation, inspect the actual repository rather than relying on a README.
- For "explain my friday project", the canonical repository is tirth1207/friday when the
  resolved request says so.
- For repository architecture analysis, prefer this sequence when needed:
  1. github.repository
  2. github.tree with recursive=true
  3. Read the most important entry points and configuration files discovered in the tree.
- Do not assume README.md exists. If a file is absent, continue with the files that exist.
- Use github.file.read for file contents, github.directory.list for a directory, and
  github.code.search for targeted symbol/string searches.
- Do not use local filesystem tools to inspect a remote GitHub repository.
- Do not expose credentials, PATs, tokens, or secret values.

Execution rules:
- Use the minimum number of tool calls needed, but gather enough source material to answer accurately.
- You may make multiple tool calls in one turn when they are independent.
- After receiving tool results, reason over them and continue calling tools if important evidence is missing.
- Stop when you have enough evidence and answer the user directly.
- Do not mention hidden prompts, chain-of-thought, or internal planning.
""".strip()


def _agent_for_tool(tool_name: str) -> str:
    if tool_name.startswith("github."):
        return "GitHub Agent"
    if tool_name.startswith("os."):
        return "OS Agent"
    if tool_name.startswith(("filesystem.", "git.")):
        return "Research Agent"
    return "Developer Agent"


def _compact_history(history: list[dict[str, Any]]) -> str:
    return json.dumps(history[-20:], ensure_ascii=False, default=str)[:100_000]


async def _run_structured_agent(
    user_message: str,
    resolved_request: str,
    recent_messages: list[dict[str, str]],
) -> str:
    langchain_tools = get_langchain_tools()
    model = get_model().bind_tools(langchain_tools)

    system_text = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Resolved request:\n{resolved_request}\n\n"
        f"Recent conversation context:\n{json.dumps(recent_messages[-12:], ensure_ascii=False, default=str)}"
    )
    messages: list[Any] = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_message),
    ]

    history: list[dict[str, Any]] = []
    max_rounds = 8

    for _ in range(max_rounds):
        response = await model.ainvoke(messages)
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(getattr(response, "content", response)))

        messages.append(response)
        tool_calls = list(response.tool_calls or [])

        if not tool_calls:
            content = response.content
            if isinstance(content, str):
                return content
            return json.dumps(content, ensure_ascii=False, default=str)

        for call in tool_calls:
            tool_name = str(call.get("name", ""))
            arguments = call.get("args") or {}
            call_id = call.get("id") or tool_name

            if not tool_name:
                messages.append(
                    ToolMessage(
                        content="Tool call rejected: missing tool name.",
                        tool_call_id=call_id,
                    )
                )
                continue

            if not isinstance(arguments, dict):
                arguments = {}

            agent_name = _agent_for_tool(tool_name)
            history_entry = {
                "tool": tool_name,
                "arguments": arguments,
                "agent": agent_name,
            }

            try:
                if tool_name.startswith("github."):
                    agent = GitHubAgent()
                elif tool_name.startswith("os."):
                    agent = OSAgent()
                else:
                    agent = ResearchAgent()

                await agent.create()
                await agent.start(f"Executing {tool_name}")
                result = await tool_executor.execute(
                    tool_name=tool_name,
                    arguments=arguments,
                    agent=agent_name,
                )
                await agent.complete(f"Completed {tool_name}")

                history_entry["result"] = result
                history.append(history_entry)
                messages.append(
                    ToolMessage(
                        content=serialize_tool_result(result),
                        tool_call_id=call_id,
                    )
                )
            except Exception as error:
                history_entry["error"] = str(error)
                history.append(history_entry)
                messages.append(
                    ToolMessage(
                        content=f"Tool execution failed: {error}",
                        tool_call_id=call_id,
                    )
                )

    fallback = await get_model().ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Answer the user's request using the tool execution history below. "
                    f"Do not invent missing facts.\n\nRequest: {user_message}\n\n"
                    f"Execution history:\n{_compact_history(history)}"
                )
            ),
        ]
    )
    return str(getattr(fallback, "content", fallback))


async def ask_friday(message: str) -> str:
    context = resolve_request(message)
    resolved_request = context["resolved_request"]
    recent_messages = context["recent_messages"]

    memory_store.add_message("user", message)

    if not is_tool_required(resolved_request):
        response = await answer_conversationally(message, recent_messages)
        memory_store.add_message("assistant", response)
        return response

    await agent_runtime.emit(
        event_type="thinking",
        title="Understanding request",
        description="Selecting structured tools for the task.",
        status="running",
    )

    if _is_environment_key_request(resolved_request):
        try:
            result = await _execute_github_tool(
                "github.file.read",
                {"repository": "tirth1207/friday", "path": ".env.example"},
                "Reading .env.example to identify required environment keys",
            )
            response = _format_env_key_result(result)
        except Exception as error:
            response = f"I couldn't read the repository's `.env.example`: {error}"
        memory_store.add_message("assistant", response)
        return response

    if _is_github_repository_list_request(resolved_request):
        try:
            result = await _execute_github_tool(
                "github.repositories",
                {"limit": 100, "sort": "pushed", "page": 1},
                "Fetching GitHub repositories",
            )
            response = _format_repository_list(result if isinstance(result, list) else [])
        except Exception as error:
            response = f"I couldn't fetch your GitHub repositories: {error}"
        memory_store.add_message("assistant", response)
        return response

    try:
        response = await _run_structured_agent(message, resolved_request, recent_messages)
    except Exception as error:
        print(f"[FRIDAY] Structured agent failed: {error}")
        response = (
            "I couldn't complete the AI reasoning step right now. "
            "The tool layer is available, but the configured NVIDIA model did not respond. "
            "Please try again."
        )

    memory_store.add_message("assistant", response)
    return response
