import json
import re
from typing import Any, Optional

from pydantic import BaseModel

import tools  # noqa: F401 - registers tools
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
    "get", "retrieve", "find",
)
GITHUB_ACTION_TERMS = (
    "github", "repo", "repository", "repositories", "commit", "commits", "profile",
    "followers", "following", "stars", "issues", "pull request", "activity",
)
OS_TARGET_TERMS = (
    "os", "operating system", "computer", "pc", "machine", "system", "process",
    "processes", "cpu", "memory", "ram", "disk", "storage", "hostname", "username",
)
OS_ACTION_TERMS = (
    "inspect", "check", "show", "get", "list", "fetch", "status", "info", "information",
    "usage", "running", "current",
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

    # Natural GitHub requests such as "show my GitHub repos" or "fetch my commits".
    if _contains_term(clean, ("github",)) and (
        _contains_term(clean, GITHUB_ACTION_TERMS) or "my github" in clean
    ):
        return True

    # OS inspection requests should use the safe OS specialist.
    if _contains_term(clean, OS_TARGET_TERMS) and _contains_term(clean, OS_ACTION_TERMS):
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
    execution_history: list[dict[str, Any]],
) -> Optional[ActionStep]:
    tools_desc = json.dumps(tool_registry.list_tools(), indent=2)
    history_desc = json.dumps(execution_history, indent=2, default=str)
    prompt = f"""
You are FRIDAY's Planner and Coordinator System.

User request:
{user_request}

Execution history:
{history_desc}

Available registered tools:
{tools_desc}

Choose ONE more tool only when necessary.
Rules:
1. Never invent tools. Use only registered tools.
2. Never repeat a successful identical tool call.
3. For GitHub data, use github.* tools and agent_name "GitHub Agent".
4. For safe computer/OS inspection, use os.* tools and agent_name "OS Agent".
5. For project/filesystem/Git work, use Research Agent or Developer Agent.
6. Do not expose credentials or environment variables.
7. If complete, return exactly DONE.
8. Otherwise return exactly one JSON object:
{{"tool":"<registered tool>","arguments":{{}},"agent_name":"<agent>"}}
"""
    response = await call_nvidia(prompt)
    if "DONE" in response.upper() or "NO_TOOL_REQUIRED" in response.upper():
        return None
    return parse_action_from_text(response)


async def answer_conversationally(message: str) -> str:
    prompt = f"""
You are FRIDAY, a personal AI operating assistant.
Answer directly and naturally:
{message}
Do not mention tools, agents, planning, execution traces, or internal systems.
"""
    return await call_nvidia(prompt)


async def ask_friday(message: str) -> str:
    memory_store.add_message("user", message)

    if not is_tool_required(message):
        print(f"[ORCHESTRATOR] Direct conversation path: '{message}'")
        response = await answer_conversationally(message)
        memory_store.add_message("assistant", response)
        return response

    print(f"[ORCHESTRATOR] Tool-capable task detected: '{message}'")
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
        action = await determine_next_action(message, execution_history)
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
            if action.tool in {"filesystem.create", "filesystem.write"}:
                filepath = action.arguments.get("path")
                if filepath:
                    created_or_modified_files.add(filepath)
            await agent_obj.complete(f"Successfully completed {action.tool}.")
        except Exception as error:
            execution_history.append({
                "step": step_count, "agent": agent_obj.name,
                "tool": action.tool, "error": str(error),
            })
            await agent_obj.complete(f"Tool execution failed: {error}")
            break

    if created_or_modified_files:
        await qa.create()
        await qa.start("Verifying files changed by FRIDAY.")
        for filepath in created_or_modified_files:
            try:
                content = await tool_executor.execute(
                    tool_name="filesystem.read", arguments={"path": filepath}, agent=qa.name,
                )
                await agent_runtime.verify(
                    title="File verification successful",
                    description=f"Verified content of {filepath}.",
                    agent=qa.name, success=True,
                    metadata={"path": filepath, "preview": str(content)[:200]},
                )
                execution_history.append({
                    "step": "verification", "agent": qa.name,
                    "verified_file": filepath, "content": content,
                })
            except Exception as error:
                await agent_runtime.verify(
                    title="File verification failed",
                    description=f"Failed to verify {filepath}: {error}",
                    agent=qa.name, success=False,
                )
        await qa.complete("Verification process complete.")

    await agent_runtime.emit(
        event_type="thinking", title="Generating final response",
        description="Synthesizing actual execution results.", status="running",
    )
    final_prompt = f"""
You are FRIDAY.
User request: {message}
Execution results:
{json.dumps(execution_history, indent=2, default=str)}
Respond clearly and concisely using only actual execution results.
Do not expose private chain-of-thought, credentials, tokens, or internal secrets.
If execution failed, explain the failure honestly.
"""
    final_response = await call_nvidia(final_prompt)
    await agent_runtime.emit(
        event_type="thinking", title="Response ready",
        description="Task response generated.", status="completed",
    )
    memory_store.add_message("assistant", final_response)
    return final_response
