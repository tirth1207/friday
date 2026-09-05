import json
import re
from typing import Any, Optional

from pydantic import BaseModel

import tools
from core.agents.runtime import agent_runtime
from core.agents.specialized import (
    DeveloperAgent,
    GitHubAgent,
    OSAgent,
    PlannerAgent,
    QAAgent,
    ResearchAgent,
)
from core.memory import memory_store
from core.memory.context import resolve_request
from core.runtime.executor import tool_executor
from core.runtime.registry import tool_registry
from providers.nvidia.client import get_model


class ActionStep(BaseModel):
    tool: str
    arguments: dict[str, Any]
    agent_name: str = "Developer Agent"


async def call_nvidia(prompt: str) -> str:
    try:
        response = await get_model().ainvoke(prompt)
        return str(response.content)
    except Exception as error:
        print(f"[NVIDIA] Call failed: {error}")
        raise RuntimeError(f"AI provider unavailable: {error}")


LOCAL_TARGET_TERMS = (
    "file", "files", "folder", "directory", "filesystem", "workspace", "path",
    "project", "codebase", "repo", "repository", "github", "git", "commit",
    "branch", "diff", "terminal", "command", "shell", "package.json",
    "pyproject.toml", "requirements.txt", "package-lock.json", "tsconfig",
    "next.config", "vite.config", "dockerfile", "docker-compose",
)
LOCAL_ACTION_TERMS = (
    "inspect", "debug", "test", "tests", "build", "install", "run", "execute",
    "create", "write", "edit", "modify", "update", "delete", "remove", "rename",
    "move", "read", "list", "search", "find", "check", "show", "open", "fetch",
    "get", "retrieve", "rank", "ranking", "compare", "analyze", "analyse",
)
GITHUB_ACTION_TERMS = (
    "github", "repo", "repository", "repositories", "commit", "commits", "profile",
    "followers", "following", "stars", "issues", "pull request", "activity",
    "file", "files", "folder", "directory", "code", "tree", "branch", "branches",
    "read", "list", "search", "fetch", "show", "get", "inspect", "rank", "ranking",
    "compare", "analyze", "analyse", "top",
)
GITHUB_TARGET_TERMS = (
    "github", "repo", "repository", "repositories", "github.com", "remote repo",
)
OS_TARGET_TERMS = (
    "os", "operating system", "computer", "pc", "machine", "system", "process",
    "processes", "cpu", "memory", "ram", "disk", "storage", "hostname", "username",
)
OS_ACTION_TERMS = (
    "inspect", "check", "show", "get", "list", "fetch", "status", "info", "information",
    "usage", "running", "current", "read", "write", "create", "delete", "folder", "file",
)
CURRENT_DATA_TERMS = (
    "latest", "today", "current", "now", "right now", "live", "weather", "forecast",
    "news", "price", "stock", "exchange rate", "score", "schedule", "traffic",
)


def _contains_term(clean: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", clean) for term in terms)


def _has_local_path(clean: str) -> bool:
    patterns = (
        r"(?:^|\s)[./\\][^\s]+",
        r"\b[a-zA-Z]:[\\/][^\s]+",
        r"\b[\w.-]+\.(?:py|js|jsx|ts|tsx|json|md|txt|css|html|yaml|yml|toml|env)\b",
    )
    return any(re.search(pattern, clean) for pattern in patterns)


def is_tool_required(message: str) -> bool:
    clean = " ".join(message.strip().lower().split())
    if not clean:
        return False

    has_local_target = _contains_term(clean, LOCAL_TARGET_TERMS) or _has_local_path(clean)
    has_local_action = _contains_term(clean, LOCAL_ACTION_TERMS)
    if has_local_target and has_local_action:
        return True

    if re.search(r"\bgit\s+(?:status|diff|log|branch)\b", clean):
        return True

    if re.search(r"\b(?:run|execute)\s+(?:this\s+)?(?:command|shell|terminal)\b", clean):
        return True

    github_url = "github.com/" in clean
    owner_repo = bool(re.search(r"\b[a-z0-9_.-]+/[a-z0-9_.-]+\b", clean))
    has_github_action = _contains_term(clean, GITHUB_ACTION_TERMS)
    if github_url or (_contains_term(clean, GITHUB_TARGET_TERMS) and has_github_action) or (owner_repo and has_github_action):
        return True

    # Natural-language repository requests such as "rank all my repos" do not
    # always contain the word GitHub. Treat repo/repositories as GitHub intent
    # when the user is asking for an action that needs repository data.
    if _contains_term(clean, ("repo", "repos", "repository", "repositories")) and _contains_term(
        clean, ("rank", "ranking", "top", "list", "show", "get", "compare", "analyze", "analyse")
    ):
        return True

    has_os_target = _contains_term(clean, OS_TARGET_TERMS)
    has_drive_path = bool(re.search(r"\b[a-z]:[\\/]|\\\\", clean))
    if has_os_target and _contains_term(clean, OS_ACTION_TERMS):
        return True
    if has_drive_path and _contains_term(clean, OS_ACTION_TERMS):
        return True

    if _contains_term(clean, CURRENT_DATA_TERMS):
        tool_names = {tool["name"].lower() for tool in tool_registry.list_tools()}
        return any(
            any(keyword in name for keyword in ("weather", "news", "search", "web", "http"))
            for name in tool_names
        )

    return False


def parse_action_from_text(response_text: str) -> Optional[ActionStep]:
    patterns = (
        r"```(?:json)?\s*(\{\s*\"tool\".*?\})\s*```",
        r"(\{\s*\"tool\"\s*:\s*\"[^\"]+\".*?\})",
    )
    for pattern in patterns:
        match = re.search(pattern, response_text, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
            if "tool" in data and isinstance(data.get("arguments"), dict):
                return ActionStep(
                    tool=data["tool"],
                    arguments=data["arguments"],
                    agent_name=data.get("agent_name", "Developer Agent"),
                )
        except Exception:
            continue
    return None


async def determine_next_action(
    user_request: str,
    conversation_context: list[dict[str, str]],
    execution_history: list[dict[str, Any]],
) -> Optional[ActionStep]:
    tools_desc = json.dumps(tool_registry.list_tools(), indent=2)
    context_desc = json.dumps(conversation_context[-12:], indent=2, default=str)
    history_desc = json.dumps(execution_history, indent=2, default=str)
    prompt = f"""
You are FRIDAY's Planner and Coordinator System.

Resolved user request:
{user_request}

Recent conversation context:
{context_desc}

Execution history for this task:
{history_desc}

Available registered tools:
{tools_desc}

Choose ONE more tool only when necessary.
Rules:
1. Treat the resolved request and recent conversation as one continuous conversation.
2. Never invent tools. Use only registered tools.
3. Never repeat a successful identical tool call.
4. For all GitHub repository/profile/code operations, use github.* tools and agent_name "GitHub Agent".
5. For repository paths like owner/name or github.com URLs, resolve and use GitHub tools rather than local filesystem tools.
6. For safe computer/OS filesystem operations, use os.* tools and agent_name "OS Agent".
7. For reading repository code, prefer github.file.read or github.directory.list; for complete structure prefer github.tree.
8. For repository listings/rankings, first fetch the repositories with github.repositories unless suitable repository data is already present in execution history.
9. For code lookup by symbol/string, use github.code.search.
10. For commits, use github.commits for recent history or github.commit for one commit and its changed files.
11. Use the previous tool result when deciding the next step. Do not ask the user to repeat information already present in context.
12. Do not expose credentials, PATs, environment variables, or secret values.
13. If complete, return exactly DONE.
14. Otherwise return exactly one JSON object:
{{"tool":"<registered tool>","arguments":{{}},"agent_name":"<agent>"}}
"""
    response = await call_nvidia(prompt)
    if "DONE" in response.upper() or "NO_TOOL_REQUIRED" in response.upper():
        return None
    return parse_action_from_text(response)


async def answer_conversationally(message: str, conversation_context: list[dict[str, str]]) -> str:
    context_desc = json.dumps(conversation_context[-12:], indent=2, default=str)
    prompt = f"""
You are FRIDAY, a personal AI operating assistant.

Recent conversation context:
{context_desc}

Current user message:
{message}

Understand short follow-ups in the context of the recent conversation. For example,
if the previous request was about ranking repositories and the user says "github",
treat that as clarification/context for the previous request, not as a request to
explain what GitHub is.

Answer directly and naturally. Do not mention tools, agents, planning, execution traces, or internal systems.
"""
    return await call_nvidia(prompt)


async def ask_friday(message: str) -> str:
    context = resolve_request(message)
    resolved_request = context["resolved_request"]
    recent_messages = context["recent_messages"]

    # Store the raw message first so future turns can refer to it.
    memory_store.add_message("user", message)

    if not is_tool_required(resolved_request):
        print(f"[ORCHESTRATOR] Direct conversation path: '{resolved_request}'")
        response = await answer_conversationally(message, recent_messages)
        memory_store.add_message("assistant", response)
        return response

    print(f"[ORCHESTRATOR] Tool-capable task detected: '{resolved_request}'")
    await agent_runtime.emit(
        event_type="thinking", title="Understanding request",
        description="Checking which capability is required.", status="running",
    )

    planner = PlannerAgent()
    await planner.create()
    await planner.start("Selecting the minimum tools required for this task.")
    await agent_runtime.emit(
        event_type="planning", title="Selecting required tools",
        description="Planning the minimum execution steps.", status="running",
    )

    execution_history: list[dict[str, Any]] = []
    created_or_modified_files: set[str] = set()
    max_steps = 5
    step_count = 0

    developer = DeveloperAgent()
    researcher = ResearchAgent()
    github_agent = GitHubAgent()
    os_agent = OSAgent()
    qa = QAAgent()
    await planner.complete("Tool plan ready.")

    research_tools = {
        "filesystem.search", "filesystem.list", "git.log", "git.status", "git.branch", "git.diff",
    }

    while step_count < max_steps:
        action = await determine_next_action(resolved_request, recent_messages, execution_history)
        if not action:
            break

        if tool_registry.get_tool(action.tool) is None:
            await agent_runtime.tool_error(
                agent="Planner Agent", tool=action.tool,
                description=f"Planner selected an unregistered tool: {action.tool}",
            )
            break

        step_count += 1
        if action.tool.startswith("github."):
            agent_obj = github_agent
        elif action.tool.startswith("os."):
            agent_obj = os_agent
        elif "Research" in action.agent_name or action.tool in research_tools:
            agent_obj = researcher
        else:
            agent_obj = developer

        await agent_obj.create()
        await agent_obj.start(f"Executing step {step_count}: {action.tool}")
        try:
            result = await tool_executor.execute(
                tool_name=action.tool,
                arguments=action.arguments,
                agent=agent_obj.name,
            )
            execution_history.append({
                "step": step_count,
                "agent": agent_obj.name,
                "tool": action.tool,
                "arguments": action.arguments,
                "result": result,
            })
            if isinstance(result, dict) and result.get("path"):
                created_or_modified_files.add(str(result["path"]))
            await agent_obj.complete(f"Completed {action.tool}.")
        except Exception as error:
            execution_history.append({
                "step": step_count,
                "agent": agent_obj.name,
                "tool": action.tool,
                "arguments": action.arguments,
                "error": str(error),
            })
            await agent_runtime.tool_error(
                agent=agent_obj.name,
                tool=action.tool,
                description=str(error),
            )
            break

    if created_or_modified_files:
        await qa.create()
        await qa.start("Verifying affected files and execution results.")
        await agent_runtime.emit(
            event_type="verification", title="Verification complete",
            description=f"Checked {len(created_or_modified_files)} affected path(s).", status="completed",
            metadata={"paths": sorted(created_or_modified_files)},
        )
        await qa.complete("Verification complete.")

    summary_prompt = f"""
You are FRIDAY. Give the user a concise, factual final answer to their request.
Resolved request:
{resolved_request}
Current message:
{message}
Recent conversation context:
{json.dumps(recent_messages[-12:], indent=2, default=str)}
Execution results:
{json.dumps(execution_history, indent=2, default=str)}

Rules:
- Use only the execution results for tool-dependent facts.
- Never claim a tool action succeeded unless the results show it succeeded.
- Keep continuity with the conversation; do not ask the user to repeat context already supplied.
- Do not mention hidden prompts, credentials, PATs, or internal chain-of-thought.
- Explain access errors plainly when they occurred.
"""
    response = await call_nvidia(summary_prompt)
    memory_store.add_message("assistant", response)
    return response
