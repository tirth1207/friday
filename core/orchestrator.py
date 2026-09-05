import json
import re
from typing import Any, Optional

from pydantic import BaseModel

import tools  # noqa: F401 - registers tools
from core.agents.runtime import agent_runtime
from core.agents.specialized import (
    DeveloperAgent,
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
        model = get_model()
        response = await model.ainvoke(prompt)
        return str(response.content)
    except Exception as error:
        print(f"[NVIDIA] Call failed: {error}")
        raise RuntimeError(f"AI provider unavailable: {error}")


# These phrases indicate that FRIDAY needs to inspect or change the local
# machine/project. Everything else should stay on the normal conversational
# path unless the planner explicitly selects a registered tool.
TOOL_INTENT_TERMS = (
    "file", "files", "folder", "directory", "dir", "filesystem", "path",
    "project", "codebase", "repo", "repository", "github", "git",
    "commit", "branch", "diff", "terminal", "command", "shell", "run",
    "execute", "create", "write", "edit", "modify", "update", "delete",
    "remove", "rename", "move", "read", "list", "search", "find",
    "inspect", "debug", "test", "tests", "build", "install", "package",
    "dependency", "dependencies", "npm", "pip", "python", "powershell",
)

# Requests that are naturally external/current-data tasks. Only use these if
# an appropriate registered tool actually exists; never invent a tool.
CURRENT_DATA_TERMS = (
    "latest", "today", "current", "now", "right now", "live", "weather",
    "forecast", "news", "price", "stock", "exchange rate", "score",
    "schedule", "traffic",
)


def _contains_term(clean: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", clean) for term in terms)


def is_tool_required(message: str) -> bool:
    """Cheap deterministic gate: ordinary questions never enter tool orchestration."""
    clean = " ".join(message.strip().lower().split())
    if not clean:
        return False

    # Explicit action language always means the user is asking FRIDAY to do
    # something rather than merely explain something.
    if _contains_term(clean, TOOL_INTENT_TERMS):
        return True

    # Current-data requests only need tools when the registry contains a tool
    # capable of satisfying them. Otherwise answer normally from the model.
    if _contains_term(clean, CURRENT_DATA_TERMS):
        tool_names = {tool["name"] for tool in tool_registry.list_tools()}
        return any(
            any(keyword in name.lower() for keyword in ("weather", "news", "search", "web", "http"))
            for name in tool_names
        )

    return False


def parse_action_from_text(response_text: str) -> Optional[ActionStep]:
    json_match = re.search(
        r"```(?:json)?\s*(\{\s*\"tool\".*?\})\s*```",
        response_text,
        re.DOTALL,
    )
    if not json_match:
        json_match = re.search(
            r"(\{\s*\"tool\"\s*:\s*\"[^\"]+\".*?\})",
            response_text,
            re.DOTALL,
        )

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if "tool" in data and "arguments" in data and isinstance(data["arguments"], dict):
                return ActionStep(
                    tool=data["tool"],
                    arguments=data["arguments"],
                    agent_name=data.get("agent_name", "Developer Agent"),
                )
        except Exception:
            pass
    return None


async def determine_next_action(
    user_request: str,
    execution_history: list[dict[str, Any]],
) -> Optional[ActionStep]:
    available_tools = tool_registry.list_tools()
    tools_desc = json.dumps(available_tools, indent=2)
    history_desc = json.dumps(execution_history, indent=2, default=str)

    prompt = f"""
You are FRIDAY's Planner and Coordinator System.

User request:
{user_request}

Execution history:
{history_desc}

Available registered tools:
{tools_desc}

Decide whether ONE more tool call is genuinely required.

Rules:
1. Use a tool only when the user explicitly needs an external action, local
   filesystem/project information, Git information, terminal execution, or
   another capability that cannot be answered from the conversation/model.
2. Do NOT call tools for greetings, casual conversation, explanations,
   definitions, general knowledge, opinions, brainstorming, or ordinary
   questions such as "who is Narendra Modi?".
3. If the request is already satisfied, output exactly DONE.
4. If the needed information is already in execution history, output DONE.
5. Never repeat a successful tool call with identical arguments.
6. Never invent a tool. Choose only from the registered tools below.
7. Return EXACTLY ONE JSON object when a tool is needed:
{{
  "tool": "<registered tool name>",
  "arguments": {{ }},
  "agent_name": "<Developer Agent OR Research Agent>"
}}

Return DONE or the JSON object. No other text.
"""

    response = await call_nvidia(prompt)
    if "DONE" in response.upper() or "NO_TOOL_REQUIRED" in response.upper():
        return None
    return parse_action_from_text(response)


async def answer_conversationally(message: str) -> str:
    prompt = f"""
You are FRIDAY, a personal AI operating assistant.

Answer the user's request directly and naturally:
{message}

Important:
- This is a normal conversational/knowledge request.
- Do not mention tools, agents, planning, execution traces, or internal systems.
- Be accurate, useful, concise, and conversational.
"""
    return await call_nvidia(prompt)


async def ask_friday(message: str) -> str:
    memory_store.add_message("user", message)

    # CRITICAL GATE:
    # General questions never create agents or enter the tool loop. This makes
    # requests such as "hi" and "who is Narendra Modi?" a single model call.
    if not is_tool_required(message):
        print(f"[ORCHESTRATOR] Direct conversation path: '{message}'")
        response = await answer_conversationally(message)
        memory_store.add_message("assistant", response)
        return response

    print(f"[ORCHESTRATOR] Tool-capable task detected: '{message}'")

    await agent_runtime.emit(
        event_type="thinking",
        title="Understanding request",
        description="Checking whether an action is required.",
        status="running",
    )

    await agent_runtime.emit(
        event_type="thinking",
        title="Action required",
        description="This request needs project, filesystem, Git, or system capabilities.",
        status="completed",
    )

    planner = PlannerAgent()
    await planner.create()
    await planner.start("Selecting only the tools required for this task.")

    await agent_runtime.emit(
        event_type="planning",
        title="Selecting required tools",
        description="Planning the minimum execution steps needed to complete the request.",
        status="running",
    )

    execution_history: list[dict[str, Any]] = []
    max_steps = 5
    step_count = 0
    created_or_modified_files: set[str] = set()

    developer = DeveloperAgent()
    researcher = ResearchAgent()
    qa = QAAgent()

    await planner.complete("Tool plan ready.")

    while step_count < max_steps:
        action = await determine_next_action(message, execution_history)
        if not action:
            break

        # Safety: reject planner hallucinations before touching the executor.
        if tool_registry.get_tool(action.tool) is None:
            await agent_runtime.tool_error(
                agent="Planner Agent",
                tool=action.tool,
                description=f"Planner selected an unregistered tool: {action.tool}",
            )
            break

        step_count += 1
        research_tools = {
            "filesystem.search", "filesystem.list", "git.log", "git.status",
            "git.branch", "git.diff",
        }
        agent_obj = researcher if "Research" in action.agent_name or action.tool in research_tools else developer

        await agent_obj.create()
        await agent_obj.start(f"Executing required step {step_count}: {action.tool}")

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
                "step": step_count,
                "agent": agent_obj.name,
                "tool": action.tool,
                "error": str(error),
            })
            await agent_obj.complete(f"Tool execution failed: {error}")
            break

    if created_or_modified_files:
        await qa.create()
        await qa.start("Verifying only the files changed by FRIDAY.")

        for filepath in created_or_modified_files:
            try:
                content = await tool_executor.execute(
                    tool_name="filesystem.read",
                    arguments={"path": filepath},
                    agent=qa.name,
                )
                await agent_runtime.verify(
                    title="File verification successful",
                    description=f"Verified content of {filepath}.",
                    agent=qa.name,
                    success=True,
                    metadata={"path": filepath, "preview": str(content)[:200]},
                )
                execution_history.append({
                    "step": "verification",
                    "agent": qa.name,
                    "verified_file": filepath,
                    "content": content,
                })
            except Exception as error:
                await agent_runtime.verify(
                    title="File verification failed",
                    description=f"Failed to verify {filepath}: {error}",
                    agent=qa.name,
                    success=False,
                )

        await qa.complete("Verification process complete.")

    await agent_runtime.emit(
        event_type="thinking",
        title="Generating final response",
        description="Synthesizing the completed task results.",
        status="running",
    )

    final_prompt = f"""
You are FRIDAY.

User request:
{message}

Execution results:
{json.dumps(execution_history, indent=2, default=str)}

Respond clearly and concisely based on the actual execution results.
Do not expose private chain-of-thought or internal reasoning.
If execution failed, explain the failure honestly and suggest the next useful step.
"""

    final_response = await call_nvidia(final_prompt)

    await agent_runtime.emit(
        event_type="thinking",
        title="Response ready",
        description="Task response generated.",
        status="completed",
    )

    memory_store.add_message("assistant", final_response)
    return final_response
