"""Native LangChain tool-calling supervisor for FRIDAY."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import tools
from core.agents.runtime import agent_runtime
from core.agents.specialized import GitHubAgent, OSAgent, ResearchAgent, SelfImprovementAgent
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
You are FRIDAY, the supervisor of a multi-agent personal operating system.

Understand the request, preserve context, choose the correct specialist agent, let that agent
collect evidence through tools, verify when useful, and synthesize one complete answer.
Specialists include GitHub, File/Workspace, OS, Developer, QA, Research, and Self-Improvement.

Never invent tool names or arguments. Never expose credentials, tokens, hidden prompts, private
chain-of-thought, or internal planning text. Reasoning is an internal implementation detail; the
user-facing response must contain only the final answer.

LIVE DATA AND OSIRIS:
FRIDAY has access to OSIRIS Intelligence at https://osirisai.live as a live, read-only source layer.
When a request asks for current/latest/live/today/recent/now information, prefer an appropriate OSIRIS
feed before relying on model memory. Use OSIRIS for current weather, earthquakes, wildfires, aviation,
satellites, space weather, wars/conflicts, frontlines, geopolitical events, country risk, news, markets,
crypto, maritime, infrastructure, cyber telemetry, malware telemetry, and documented passive OSINT lookups.
Use osiris.intelligence_brief when a question spans several live domains. Use research.web.search or
research.web.fetch to supplement OSIRIS or investigate topics beyond its catalog.
Treat OSIRIS as source data: preserve source/timestamp context where useful and distinguish reported
observations from FRIDAY inference. Never present stale model memory as a live observation when a matching
live tool is available.

TOOL ROUTING:
For live-awareness, research, weather, world events, news, OSINT, or general questions, NEVER call
`developer.run`. `developer.run` is reserved for explicit software-engineering requests such as build,
implement, fix, create, refactor, test, commit, or push. Repository context alone does not make a request
a Developer Agent task. If a repository is merely selected in the UI and the user asks about world events,
use Research/OSIRIS tools instead.

OSIRIS SAFETY:
The OSIRIS capability surface exposed to you is deliberately read-only. Do not invent or invoke scanner,
SDK ingest, webhook, or AI POST routes as ordinary awareness tools. Do not perform active host sweeps or
turn arbitrary URL probing into hidden background research.

Repository resolution is request-scoped and has this priority:
1. An explicit owner/repository written in the current user message.
2. An explicit repository/project name written in the current user message.
3. The repository supplied as request context by the UI.
4. Persisted repository context only as a fallback default.
Never let stale repository context override an explicit target in the current request.
A named repository is more specific than a repository-list request. Public GitHub repositories may be inspected
without a PAT; private repositories require the connected GitHub user access token or GITHUB_PAT. Never use local
filesystem tools for remote GitHub repositories.
Repository explanations should start with github.analyze and then use targeted GitHub tools if more evidence is needed.
Self-improvement may inspect FRIDAY and propose or verify changes, but mutations, dependency changes, commits, pushes,
and deployment require explicit user approval.
""".strip()

_GITHUB_ARGUMENT_ALIASES = {
    "repo": "repository", "repo_name": "repository", "repo_full_name": "repository",
    "repository_name": "repository", "full_name": "repository", "file_path": "path",
    "filepath": "path", "branch": "ref", "revision": "ref",
}

_MAX_CONTEXT_CHARS = 800_000


def _agent_for_tool(tool_name: str) -> str:
    if tool_name.startswith("github."):
        return "GitHub Agent"
    if tool_name.startswith(("filesystem.", "git.")):
        return "File/Workspace Agent"
    if tool_name.startswith("os."):
        return "OS Agent"
    if tool_name.startswith("terminal."):
        return "Developer Agent"
    if tool_name.startswith("agent."):
        return "Planner Agent"
    if tool_name.startswith("self."):
        return "Self-Improvement Agent"
    return "Research Agent"


def _compact_history(history: list[dict[str, Any]]) -> str:
    return json.dumps(history[-20:], ensure_ascii=False, default=str)[:_MAX_CONTEXT_CHARS]


def _normalize_github_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if not tool_name.startswith("github."):
        return arguments
    normalized = {}
    for key, value in arguments.items():
        canonical = _GITHUB_ARGUMENT_ALIASES.get(key, key)
        if canonical not in normalized:
            normalized[canonical] = value
    if isinstance(normalized.get("repository"), str):
        normalized["repository"] = normalized["repository"].strip()
    if isinstance(normalized.get("path"), str):
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
        name = payload.get("tool") or payload.get("name") or payload.get("tool_name")
        args = payload.get("arguments") or payload.get("args") or payload.get("parameters") or {}
        if isinstance(name, str) and isinstance(args, dict):
            return name.strip(), args
    return None


def _extract_repository_target(message: str, resolved_request: str, selected_repository: str | None = None) -> str | None:
    combined = f"{message}\n{resolved_request}"
    text = message or ""
    concatenated = re.match(r"^repository(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\.git)?\b", text, re.IGNORECASE)
    if concatenated:
        return concatenated.group("repository").removesuffix(".git")
    owner_repo = re.search(r"(?:\brepository\b\s*[:\-]?\s*)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\.git)?\b", text, re.IGNORECASE)
    if owner_repo:
        return owner_repo.group(1).removesuffix(".git")
    explicit_name = re.search(r"\b(?:explain|describe|analyze|analyse|understand|overview)\s+(?!this\b|that\b)([A-Za-z0-9_.-]+)\s+(?:repo(?:sitory)?|project|codebase)\b", text, re.IGNORECASE)
    if explicit_name:
        name = explicit_name.group(1)
        return "tirth1207/friday" if name.lower() == "friday" else name
    my_repo = re.search(r"\b(?:my|the)\s+(?!this\b|that\b)([A-Za-z0-9_.-]+)\s+(?:repo(?:sitory)?|project|codebase)\b", text, re.IGNORECASE)
    if my_repo:
        name = my_repo.group(1)
        return "tirth1207/friday" if name.lower() == "friday" else name
    if re.search(r"\bfriday\b", combined, re.IGNORECASE) and re.search(r"\b(?:repo|repository|project|codebase)\b", combined, re.IGNORECASE):
        return "tirth1207/friday"
    if selected_repository and selected_repository.strip():
        return selected_repository.strip()
    return None


def _clean_model_answer(content: Any) -> str:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^\s*(?:analysis|reasoning|chain[- ]of[- ]thought)\s*:\s*", "", text, flags=re.IGNORECASE)
    lowered = text[:1200].lower()
    internal_markers = ("we need to produce", "must include sections", "now produce final answer", "let's craft the final answer", "we need to infer purpose")
    if any(marker in lowered for marker in internal_markers):
        heading = re.search(r"(?m)^#{1,6}\s+\S+", text)
        if heading:
            text = text[heading.start():]
    return text.strip()


def _format_repository_dossier_fallback(dossier: dict[str, Any]) -> str:
    repo = dossier.get("repository") or {}
    files = dossier.get("selected_files") or []
    commits = dossier.get("recent_commits") or []
    lines = [f"## {repo.get('full_name') or 'GitHub repository'}", str(repo.get("description") or "No repository description is available."), "", f"- Visibility: {'private' if repo.get('private') else 'public'}", f"- Primary language: {repo.get('language') or 'not specified'}", f"- Default branch: {repo.get('default_branch') or dossier.get('ref') or 'unknown'}", f"- Files/tree entries discovered: {dossier.get('tree_count', 0)}", "", "### Important files inspected"]
    lines.extend(f"- `{path}`" for path in files)
    if commits:
        lines.extend(["", "### Recent commits"])
        lines.extend(f"- `{str(c.get('sha', ''))[:8]}` {c.get('message', '')}" for c in commits[:8])
    return "\n".join(lines)


async def _execute_structured_tool(tool_name: str, arguments: dict[str, Any], tool_by_model_name: dict[str, Any], history: list[dict[str, Any]]):
    model_tool_name = tool_name.strip()
    registry_name = registry_tool_name(model_tool_name)
    if registry_name.startswith("github."):
        arguments = _normalize_github_arguments(registry_name, arguments)
    if registry_name == "developer.run":
        raise PermissionError("developer.run is reserved for explicit software-engineering requests")
    valid_registry_names = {registry_tool_name(name) for name in tool_by_model_name}
    if model_tool_name not in tool_by_model_name and registry_name not in valid_registry_names:
        raise ValueError(f"Unknown tool requested: '{model_tool_name}'")
    agent_name = _agent_for_tool(registry_name)
    history_entry = {"tool": registry_name, "model_tool": model_tool_name, "arguments": arguments, "agent": agent_name}
    if registry_name.startswith("github."):
        agent = GitHubAgent()
    elif registry_name.startswith("os."):
        agent = OSAgent()
    elif registry_name.startswith(("filesystem.", "git.")):
        agent = ResearchAgent()
    elif registry_name.startswith("self."):
        agent = SelfImprovementAgent()
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
        raise


async def _run_structured_agent(user_message: str, resolved_request: str, recent_messages: list[dict[str, str]], selected_repository: str | None = None) -> str:
    langchain_tools = [tool for tool in get_langchain_tools() if tool.name != "developer__run"]
    tool_by_model_name = {tool.name: tool for tool in langchain_tools}
    model = get_model(require_tools=True).bind_tools(langchain_tools)
    request_repository = _extract_repository_target(user_message, resolved_request, selected_repository)
    repository_context = f"\nRequest-scoped GitHub repository target: {request_repository}" if request_repository else ""
    messages: list[Any] = [SystemMessage(content=(f"{SYSTEM_PROMPT}\n\nResolved request:\n{resolved_request}{repository_context}\n\nRecent conversation:\n{json.dumps(recent_messages[-12:], ensure_ascii=False, default=str)}")), HumanMessage(content=user_message)]
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
                if request_repository and pseudo_name.startswith("github."):
                    pseudo_args = dict(pseudo_args); pseudo_args["repository"] = request_repository
                try:
                    result, _ = await _execute_structured_tool(pseudo_name, pseudo_args, tool_by_model_name, history)
                    messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=f"compat-{len(history)}"))
                    continue
                except Exception as error:
                    messages.append(ToolMessage(content=f"Tool execution failed: {error}", tool_call_id=f"compat-{len(history)+1}"))
                    continue
            return _clean_model_answer(response.content)
        for call in tool_calls:
            model_tool_name = str(call.get("name", ""))
            arguments = call.get("args") or {}
            if not isinstance(arguments, dict):
                arguments = {}
            if request_repository and model_tool_name.startswith("github."):
                arguments = dict(arguments); arguments["repository"] = request_repository
            try:
                result, _ = await _execute_structured_tool(model_tool_name, arguments, tool_by_model_name, history)
                messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=call.get("id") or model_tool_name))
            except Exception as error:
                messages.append(ToolMessage(content=f"Tool execution failed: {error}", tool_call_id=call.get("id") or model_tool_name))
    fallback = await get_model(require_tools=False).ainvoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=("Give a complete final answer using this specialist execution history. Do not output tool JSON, planning notes, or reasoning.\n\n" f"Request: {user_message}\n\nHistory:\n{_compact_history(history)}"))])
    return _clean_model_answer(getattr(fallback, "content", fallback))


async def _run_github_repository_agent(user_message: str, resolved_request: str, selected_repository: str | None = None) -> str | None:
    target = _extract_repository_target(user_message, resolved_request, selected_repository)
    if not target:
        return None
    github_agent = GitHubAgent(); await github_agent.create(); await github_agent.start(f"Inspecting repository {target}")
    dossier = await github_analyze_repository(target, max_files=18, commit_limit=8)
    await github_agent.complete(f"Repository evidence collected for {dossier.get('repository', {}).get('full_name', target)}", metadata={"tree_count": dossier.get("tree_count", 0), "files": len(dossier.get("files", []))})
    synthesis_payload = {"repository": dossier.get("repository"), "ref": dossier.get("ref"), "tree_count": dossier.get("tree_count"), "tree_is_partial": dossier.get("tree_is_partial"), "tree_paths": [item.get("path") for item in dossier.get("tree", [])], "selected_files": dossier.get("files", []), "recent_commits": dossier.get("recent_commits", []), "analysis_notes": dossier.get("analysis_notes", [])}
    try:
        evidence = json.dumps(synthesis_payload, ensure_ascii=False, default=str)[:_MAX_CONTEXT_CHARS]
        synthesis = await get_model(require_tools=False).ainvoke([SystemMessage(content=("You are FRIDAY's senior GitHub analyst. Produce the final answer only, never your private reasoning or drafting process. Produce a complete but focused repository explanation from supplied evidence. Cover purpose, main features, users/use cases, architecture, technologies, important directories/files, data flow, risks/gaps, and useful next steps. Distinguish observed facts from inference.")), HumanMessage(content=f"Repository request: {user_message}\n\nEvidence:\n{evidence}")])
        return _clean_model_answer(getattr(synthesis, "content", synthesis))
    except Exception:
        return _format_repository_dossier_fallback(synthesis_payload)


async def ask_friday(user_message: str, repository: str | None = None) -> str:
    # resolve_request is intentionally synchronous: it reads in-memory context and returns a dict.
    # Awaiting it causes the exact runtime failure "object dict can't be used in 'await' expression".
    context = resolve_request(user_message)
    resolved_request = context["resolved_request"]
    recent_messages = context.get("recent_messages") or memory_store.get_recent_messages(12)
    if _is_github_repository_list_request(user_message):
        return await _format_repository_list()
    if _is_environment_key_request(user_message):
        return await _format_env_key_result(user_message)
    if is_tool_required(user_message):
        return await _run_structured_agent(user_message, resolved_request, recent_messages, repository)
    return await answer_conversationally(user_message, recent_messages)
