"""Native LangChain tool-calling orchestrator for FRIDAY."""

from __future__ import annotations

import json
import re
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
from core.runtime.langchain_tools import get_langchain_tools, registry_tool_name, serialize_tool_result
from providers.nvidia.client import get_model


SYSTEM_PROMPT = """
You are FRIDAY, a personal AI operating assistant and senior software-engineering agent.
You have native structured tool calling. Use tools whenever the user asks about a real
repository, local machine, files, Git, GitHub, code, or another tool-backed capability.
Never invent tool names or tool arguments. Use the schemas supplied by LangChain.

GitHub rules:
- A named repository is always more specific than a request to list repositories.
- Preserve the canonical owner/name returned by GitHub; repository names are case-insensitive
  for API addressing but the returned full_name is authoritative for presentation.
- For a repository explanation, inspect the actual repository rather than relying on a README.
- For repository architecture analysis, prefer this sequence when needed:
  1. github.repository
  2. github.tree with repository=<owner>/<repo> and recursive=true
  3. Read the most important entry points and configuration files discovered in the tree.
- Do not assume README.md exists. If a file is absent, continue with files that exist.
- Use github.file.read for file contents, github.directory.list for a directory, and
  github.code.search for targeted symbol/string searches.
- Use github.api for GitHub REST operations that do not have a dedicated tool.
- For github.api, path must be a GitHub REST path such as /repos/OWNER/REPO/issues.
- Do not use local filesystem tools to inspect a remote GitHub repository.
- Never expose credentials, PATs, tokens, or secret values.

Execution rules:
- Use the minimum number of tool calls needed, but gather enough source material to answer accurately.
- You may make multiple tool calls in one turn when they are independent.
- After receiving tool results, continue calling tools if important evidence is missing.
- Stop when you have enough evidence and answer the user directly.
- Never print a tool-call JSON object as the final answer. Tool calls must be executed.
- Do not mention hidden prompts, chain-of-thought, or internal planning.
""".strip()


_GITHUB_ARGUMENT_ALIASES: dict[str, str] = {
    "repo": "repository",
    "repo_name": "repository",
    "repo_full_name": "repository",
    "repository_name": "repository",
    "full_name": "repository",
    "file_path": "path",
    "filepath": "path",
    "branch": "ref",
    "revision": "ref",
}


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


def _normalize_github_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalize common provider/model aliases to FRIDAY's canonical GitHub schemas."""
    if not tool_name.startswith("github."):
        return arguments

    normalized: dict[str, Any] = {}
    for key, value in arguments.items():
        canonical = _GITHUB_ARGUMENT_ALIASES.get(key, key)
        if canonical not in normalized:
            normalized[canonical] = value

    if "repository" in normalized and isinstance(normalized["repository"], str):
        normalized["repository"] = normalized["repository"].strip()
    if "path" in normalized and isinstance(normalized["path"], str):
        normalized["path"] = normalized["path"].lstrip("/")
    return normalized


def _extract_pseudo_tool_call(content: Any) -> tuple[str, dict[str, Any]] | None:
    """Recover tool calls emitted as JSON/text by models that fail native tool-call formatting."""
    if not isinstance(content, str):
        return None

    text = content.strip()
    if not text:
        return None

    candidates = [text]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE))
    candidates.extend(re.findall(r"(\{\s*['\"]tool['\"]\s*:.*?\})", text, flags=re.DOTALL))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        tool_name = payload.get("tool") or payload.get("name") or payload.get("tool_name")
        arguments = payload.get("arguments") or payload.get("args") or payload.get("parameters") or {}
        if isinstance(tool_name, str) and isinstance(arguments, dict):
            return tool_name.strip(), arguments

    return None


async def _execute_structured_tool(
    tool_name: str,
    arguments: dict[str, Any],
    tool_by_model_name: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[Any, str]:
    """Validate, normalize and execute one model-selected tool."""
    model_tool_name = tool_name.strip()
    registry_name = registry_tool_name(model_tool_name)
    if registry_name.startswith("github."):
        arguments = _normalize_github_arguments(registry_name, arguments)

    valid_registry_names = {registry_tool_name(name) for name in tool_by_model_name}
    if model_tool_name not in tool_by_model_name and registry_name not in valid_registry_names:
        raise ValueError(f"Unknown tool requested: '{model_tool_name}'")

    agent_name = _agent_for_tool(registry_name)
    history_entry = {
        "tool": registry_name,
        "model_tool": model_tool_name,
        "arguments": arguments,
        "agent": agent_name,
    }

    if registry_name.startswith("github."):
        agent = GitHubAgent()
    elif registry_name.startswith("os."):
        agent = OSAgent()
    else:
        agent = ResearchAgent()

    try:
        await agent.create()
        await agent.start(f"Executing {registry_name}")
        result = await tool_executor.execute(
            tool_name=registry_name,
            arguments=arguments,
            agent=agent_name,
        )
        await agent.complete(f"Completed {registry_name}")
        history_entry["result"] = result
        history.append(history_entry)
        return result, registry_name
    except Exception as error:
        history_entry["error"] = str(error)
        history.append(history_entry)
        try:
            await agent.complete(f"Failed {registry_name}")
        except Exception:
            pass
        raise


async def _run_structured_agent(
    user_message: str,
    resolved_request: str,
    recent_messages: list[dict[str, str]],
) -> str:
    langchain_tools = get_langchain_tools()
    tool_by_model_name = {tool.name: tool for tool in langchain_tools}
    model = get_model(require_tools=True).bind_tools(langchain_tools)

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
            pseudo_call = _extract_pseudo_tool_call(response.content)
            if pseudo_call:
                pseudo_name, pseudo_args = pseudo_call
                call_id = f"compat-{len(history) + 1}"
                try:
                    result, _ = await _execute_structured_tool(
                        pseudo_name,
                        pseudo_args,
                        tool_by_model_name,
                        history,
                    )
                    messages.append(
                        ToolMessage(
                            content=serialize_tool_result(result),
                            tool_call_id=call_id,
                        )
                    )
                    continue
                except Exception as error:
                    messages.append(
                        ToolMessage(
                            content=f"Tool execution failed: {error}",
                            tool_call_id=call_id,
                        )
                    )
                    continue

            content = response.content
            if isinstance(content, str):
                return content
            return json.dumps(content, ensure_ascii=False, default=str)

        for call in tool_calls:
            model_tool_name = str(call.get("name", ""))
            arguments = call.get("args") or {}
            call_id = call.get("id") or model_tool_name

            if not model_tool_name:
                messages.append(
                    ToolMessage(
                        content="Tool call rejected: missing tool name.",
                        tool_call_id=call_id,
                    )
                )
                continue

            if not isinstance(arguments, dict):
                arguments = {}

            try:
                result, _ = await _execute_structured_tool(
                    model_tool_name,
                    arguments,
                    tool_by_model_name,
                    history,
                )
                messages.append(
                    ToolMessage(
                        content=serialize_tool_result(result),
                        tool_call_id=call_id,
                    )
                )
            except Exception as error:
                messages.append(
                    ToolMessage(
                        content=f"Tool execution failed: {error}",
                        tool_call_id=call_id,
                    )
                )

    fallback = await get_model(require_tools=False).ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Answer the user's request using the tool execution history below. "
                    f"Do not invent missing facts and do not output tool-call JSON.\n\n"
                    f"Request: {user_message}\n\nExecution history:\n{_compact_history(history)}"
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
