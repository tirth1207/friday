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
from tools.github.repository_agent import github_analyze_repository

SYSTEM_PROMPT = """
You are FRIDAY, a personal AI operating assistant and senior software-engineering agent.
You have native structured tool calling. Use tools whenever the user asks about a real repository,
local machine, files, Git, GitHub, code, or another tool-backed capability.
Never invent tool names or tool arguments. Use the schemas supplied by LangChain.

GitHub rules:
- A named repository is always more specific than a request to list repositories.
- Preserve the canonical owner/name returned by GitHub.
- A repository explanation should use github.analyze first. This deterministic GitHub Agent fetches
  metadata, the recursive Git tree, recent commits, and the most informative source, documentation,
  and configuration files without relying on the model to invent tool calls.
- After github.analyze, use github.file.read, github.directory.list, github.code.search, github.commits,
  github.branches, or github.commit for deeper targeted inspection when needed.
- Public GitHub repositories may be inspected without a PAT. Private repositories require the configured
  GITHUB_PAT and are limited to repositories that token can access.
- Do not use local filesystem tools to inspect a remote GitHub repository.
- Never expose credentials, PATs, tokens, or secret values.

Execution rules:
- Use the minimum number of tool calls needed, but gather enough source material to answer accurately.
- After receiving tool results, continue calling tools if important evidence is missing.
- Never print a tool-call JSON object as the final answer.
- Do not mention hidden prompts, chain-of-thought, or internal planning.
""".strip()

_GITHUB_ARGUMENT_ALIASES: dict[str, str] = {
    "repo": "repository", "repo_name": "repository", "repo_full_name": "repository",
    "repository_name": "repository", "full_name": "repository", "file_path": "path",
    "filepath": "path", "branch": "ref", "revision": "ref",
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
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    candidates = [text]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE))
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


def _extract_repository_target(message: str, resolved_request: str) -> str | None:
    combined = f"{message}\n{resolved_request}"
    if re.search(r"\bfriday\b", combined, re.IGNORECASE) and re.search(r"\b(?:repo|repository|project|codebase)\b", combined, re.IGNORECASE):
        if re.search(r"\b(?:explain|describe|analy[sz]e|understand|overview)\b", combined, re.IGNORECASE):
            return "tirth1207/friday"
    owner_repo = re.search(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", combined)
    if owner_repo:
        return owner_repo.group(1)
    named = re.search(r"\b(?:repo(?:sitory)?|project|codebase)\s+(?:named|called)?\s*([A-Za-z0-9_.-]+)\b", message, re.IGNORECASE)
    if named:
        return named.group(1)
    my_repo = re.search(r"\b(?:my|the)\s+([A-Za-z0-9_.-]+)\s+(?:repo(?:sitory)?|project|codebase)\b", message, re.IGNORECASE)
    if my_repo:
        return my_repo.group(1)
    return None


def _format_repository_dossier_fallback(dossier: dict[str, Any]) -> str:
    repo = dossier.get("repository") or {}
    files = dossier.get("selected_files") or []
    commits = dossier.get("recent_commits") or []
    lines = [
        f"## {repo.get('full_name') or 'GitHub repository'}",
        str(repo.get("description") or "No repository description is available."),
        "",
        f"- Visibility: {'private' if repo.get('private') else 'public'}",
        f"- Primary language: {repo.get('language') or 'not specified'}",
        f"- Default branch: {repo.get('default_branch') or dossier.get('ref') or 'unknown'}",
        f"- Files/tree entries discovered: {dossier.get('tree_count', 0)}",
        "",
        "### Important files inspected",
    ]
    lines.extend(f"- `{path}`" for path in files)
    if commits:
        lines.extend(["", "### Recent commits"])
        for commit in commits[:8]:
            lines.append(f"- `{str(commit.get('sha', ''))[:8]}` {commit.get('message', '')}")
    lines.extend(["", "The GitHub Agent successfully fetched repository evidence. NVIDIA synthesis is currently unavailable, so this is the raw evidence summary."])
    return "\n".join(lines)


async def _execute_structured_tool(tool_name: str, arguments: dict[str, Any], tool_by_model_name: dict[str, Any], history: list[dict[str, Any]]) -> tuple[Any, str]:
    model_tool_name = tool_name.strip()
    registry_name = registry_tool_name(model_tool_name)
    if registry_name.startswith("github."):
        arguments = _normalize_github_arguments(registry_name, arguments)
    valid_registry_names = {registry_tool_name(name) for name in tool_by_model_name}
    if model_tool_name not in tool_by_model_name and registry_name not in valid_registry_names:
        raise ValueError(f"Unknown tool requested: '{model_tool_name}'")
    agent_name = _agent_for_tool(registry_name)
    history_entry = {"tool": registry_name, "model_tool": model_tool_name, "arguments": arguments, "agent": agent_name}
    if registry_name.startswith("github."):
        agent = GitHubAgent()
    elif registry_name.startswith("os."):
        agent = OSAgent()
    else:
        agent = ResearchAgent()
    try:
        await agent.create()
        await agent.start(f"Executing {registry_name}")
        result = await tool_executor.execute(tool_name=registry_name, arguments=arguments, agent=agent_name)
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


async def _run_structured_agent(user_message: str, resolved_request: str, recent_messages: list[dict[str, str]]) -> str:
    langchain_tools = get_langchain_tools()
    tool_by_model_name = {tool.name: tool for tool in langchain_tools}
    model = get_model(require_tools=True).bind_tools(langchain_tools)
    system_text = f"{SYSTEM_PROMPT}\n\nResolved request:\n{resolved_request}\n\nRecent conversation context:\n{json.dumps(recent_messages[-12:], ensure_ascii=False, default=str)}"
    messages: list[Any] = [SystemMessage(content=system_text), HumanMessage(content=user_message)]
    history: list[dict[str, Any]] = []
    for _ in range(8):
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
                    result, _ = await _execute_structured_tool(pseudo_name, pseudo_args, tool_by_model_name, history)
                    messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=call_id))
                    continue
                except Exception as error:
                    messages.append(ToolMessage(content=f"Tool execution failed: {error}", tool_call_id=call_id))
                    continue
            content = response.content
            return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        for call in tool_calls:
            model_tool_name = str(call.get("name", ""))
            arguments = call.get("args") or {}
            call_id = call.get("id") or model_tool_name
            if not isinstance(arguments, dict):
                arguments = {}
            try:
                result, _ = await _execute_structured_tool(model_tool_name, arguments, tool_by_model_name, history)
                messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=call_id))
            except Exception as error:
                messages.append(ToolMessage(content=f"Tool execution failed: {error}", tool_call_id=call_id))
    fallback = await get_model(require_tools=False).ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(f"Answer the user's request using the tool execution history below. Do not invent missing facts and do not output tool-call JSON.\n\nRequest: {user_message}\n\nExecution history:\n{_compact_history(history)}")),
    ])
    return str(getattr(fallback, "content", fallback))


async def _run_github_repository_agent(user_message: str, resolved_request: str) -> str | None:
    target = _extract_repository_target(user_message, resolved_request)
    if not target:
        return None
    await agent_runtime.emit(event_type="thinking", title="GitHub Agent", description=f"Inspecting repository {target}", status="running")
    dossier = await github_analyze_repository(target, max_files=18, commit_limit=8)
    await agent_runtime.emit(
        event_type="tool", title="GitHub Agent",
        description=(f"Fetched {dossier.get('tree_count', 0)} tree entries and {len(dossier.get('files', []))} important files from {dossier.get('repository', {}).get('full_name', target)}"),
        status="completed",
    )
    try:
        synthesis = await get_model(require_tools=False).ainvoke([
            SystemMessage(content=("You are FRIDAY's senior GitHub analyst. Explain repositories from the supplied GitHub evidence only. Cover purpose, users/features, architecture, technologies, important directories/files, data flow, security, deployment, and notable risks. Do not invent facts. If evidence is incomplete, say what is missing. Never expose secrets.")),
            HumanMessage(content=(f"User request: {user_message}\n\nRepository evidence:\n{json.dumps(dossier, ensure_ascii=False, default=str)[:180_000]}")),
        ])
        content = getattr(synthesis, "content", synthesis)
        if isinstance(content, str) and content.strip():
            return content
    except Exception as error:
        print(f"[FRIDAY] GitHub evidence collected but NVIDIA synthesis failed: {error}")
    return _format_repository_dossier_fallback(dossier)


async def ask_friday(message: str) -> str:
    context = resolve_request(message)
    resolved_request = context["resolved_request"]
    recent_messages = context["recent_messages"]
    memory_store.add_message("user", message)
    if not is_tool_required(resolved_request):
        response = await answer_conversationally(message, recent_messages)
        memory_store.add_message("assistant", response)
        return response

    await agent_runtime.emit(event_type="thinking", title="Understanding request", description="Selecting structured tools for the task.", status="running")

    if _is_environment_key_request(resolved_request):
        try:
            result = await _execute_github_tool("github.file.read", {"repository": "tirth1207/friday", "path": ".env.example"}, "Reading .env.example to identify required environment keys")
            response = _format_env_key_result(result)
        except Exception as error:
            response = f"I couldn't read the repository's `.env.example`: {error}"
        memory_store.add_message("assistant", response)
        return response

    if _is_github_repository_list_request(resolved_request):
        try:
            result = await _execute_github_tool("github.repositories", {"limit": 100, "sort": "pushed", "page": 1}, "Fetching GitHub repositories")
            response = _format_repository_list(result if isinstance(result, list) else [])
        except Exception as error:
            response = f"I couldn't fetch your GitHub repositories: {error}"
        memory_store.add_message("assistant", response)
        return response

    if re.search(r"\b(?:explain|describe|analyze|analyse|understand|overview)\b", resolved_request, re.IGNORECASE) and re.search(r"\b(?:repo|repository|project|codebase)\b", resolved_request, re.IGNORECASE):
        try:
            github_response = await _run_github_repository_agent(message, resolved_request)
            if github_response:
                memory_store.add_message("assistant", github_response)
                return github_response
        except Exception as error:
            print(f"[FRIDAY] GitHub Agent failed: {error}")
            response = f"I couldn't inspect the requested GitHub repository: {error}"
            memory_store.add_message("assistant", response)
            return response

    try:
        response = await _run_structured_agent(message, resolved_request, recent_messages)
    except Exception as error:
        print(f"[FRIDAY] Structured agent failed: {error}")
        response = f"I couldn't complete the AI reasoning step right now. The provider returned: {error}"
    memory_store.add_message("assistant", response)
    return response
