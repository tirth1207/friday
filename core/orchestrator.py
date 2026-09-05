import json
import re
from typing import Any, Optional
from pydantic import BaseModel

import tools  # Ensure all tools are registered in tool_registry on import
from core.agents.runtime import agent_runtime
from core.memory import memory_store
from core.runtime.executor import tool_executor
from core.runtime.registry import tool_registry
from core.agents.specialized import PlannerAgent, DeveloperAgent, ResearchAgent, QAAgent
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
    except Exception as e:
        print(f"[NVIDIA] Call failed: {e}")
        raise RuntimeError(f"AI provider unavailable: {e}")


def is_simple_conversational(message: str) -> bool:
    clean = message.strip().lower()
    greetings = {
        "hi", "hello", "hey", "who are you", "what can you do", "help",
        "good morning", "good evening", "what is recursion", "explain python",
        "tell me a joke", "thanks", "thank you"
    }
    if clean in greetings or (len(clean) < 15 and not any(kw in clean for kw in ["file", "dir", "code", "read", "write", "list", "search", "create", "git", "run", "terminal", "test", "project"])):
        return True

    if (clean.startswith("explain") or clean.startswith("what is") or clean.startswith("how does")) and not any(kw in clean for kw in ["file", "dir", "project", "folder", "friday", ".py", "codebase", "repo"]):
        return True

    return False


def parse_action_from_text(response_text: str) -> Optional[ActionStep]:
    json_match = re.search(r"```(?:json)?\s*(\{\s*\"tool\".*?\})\s*```", response_text, re.DOTALL)
    if not json_match:
        json_match = re.search(r"(\{\s*\"tool\"\s*:\s*\"[^\"]+\".*?\})", response_text, re.DOTALL)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if "tool" in data and "arguments" in data and isinstance(data["arguments"], dict):
                agent_name = data.get("agent_name", "Developer Agent")
                return ActionStep(tool=data["tool"], arguments=data["arguments"], agent_name=agent_name)
        except Exception:
            pass
    return None


async def determine_next_action(user_request: str, execution_history: list[dict[str, Any]]) -> Optional[ActionStep]:
    available_tools = tool_registry.list_tools()
    tools_desc = json.dumps(available_tools, indent=2)
    history_desc = json.dumps(execution_history, indent=2, default=str)

    prompt = f"""
You are FRIDAY's Planner and Coordinator System.
The user requested: "{user_request}"

Execution History So Far:
{history_desc}

Available Registered Tools:
{tools_desc}

Determine if another tool action is required to complete the request.
Specialized Agent Roles:
- Developer Agent: filesystem.read, filesystem.write, filesystem.create, terminal.execute
- ResearchAgent: filesystem.list, filesystem.search, git.log, git.status, git.branch, git.diff

If a tool action is needed, output EXACTLY ONE JSON block:
```json
{{
  "tool": "<tool_name>",
  "arguments": {{
    "<arg_name>": "<arg_value>"
  }},
  "agent_name": "<Developer Agent OR Research Agent>"
}}
```

Rules:
- If all required information has been gathered or the action is done, reply with "DONE".
- Do NOT repeat a tool call that already succeeded with identical arguments.
"""

    response = await call_nvidia(prompt)
    if "DONE" in response or "NO_TOOL_REQUIRED" in response:
        return None

    return parse_action_from_text(response)


async def ask_friday(message: str) -> str:
    memory_store.add_message("user", message)

    # Fast-path simple conversational queries
    if is_simple_conversational(message):
        print(f"[ORCHESTRATOR] Fast-path simple conversation: '{message}'")
        system_prompt = f"You are FRIDAY, a personal AI operating assistant. The user says: '{message}'. Respond helpfully and concisely."
        response = await call_nvidia(system_prompt)
        memory_store.add_message("assistant", response)
        return response

    print(f"[ORCHESTRATOR] Starting task execution workflow for: '{message}'")

    # Step 1: Request Understanding
    await agent_runtime.emit(
        event_type="thinking",
        title="Understanding request",
        description=message,
        status="running",
    )
    await agent_runtime.emit(
        event_type="thinking",
        title="Request understood",
        description="The request has been classified.",
        status="completed",
    )

    # Step 2: Planning with Planner Agent
    planner = PlannerAgent()
    await planner.create()
    await planner.start("Creating subtasks and execution plan.")

    await agent_runtime.emit(
        event_type="planning",
        title="Creating execution plan",
        description="Determining required specialized agents and tools.",
        status="running",
    )

    execution_history = []
    max_steps = 5
    step_count = 0
    created_or_modified_files = set()

    developer = DeveloperAgent()
    researcher = ResearchAgent()
    qa = QAAgent()

    await planner.complete("Execution plan initialized.")

    # Multi-step Agent Tool Execution Loop
    while step_count < max_steps:
        action = await determine_next_action(message, execution_history)
        if not action:
            break

        step_count += 1
        agent_obj = researcher if "Research" in action.agent_name or action.tool in ["filesystem.search", "filesystem.list", "git.log", "git.status", "git.diff", "git.branch"] else developer

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

            if action.tool in ["filesystem.create", "filesystem.write"]:
                filepath = action.arguments.get("path")
                if filepath:
                    created_or_modified_files.add(filepath)

            await agent_obj.complete(f"Successfully completed {action.tool}.")

        except Exception as err:
            execution_history.append({
                "step": step_count,
                "agent": agent_obj.name,
                "tool": action.tool,
                "error": str(err),
            })
            await agent_obj.complete(f"Tool execution failed: {err}")
            break

    # Verification step with QA Agent if files were created or modified
    if created_or_modified_files:
        await qa.create()
        await qa.start("Verifying file modifications.")

        for fpath in created_or_modified_files:
            try:
                content = await tool_executor.execute(
                    tool_name="filesystem.read",
                    arguments={"path": fpath},
                    agent=qa.name,
                )
                await agent_runtime.verify(
                    title="File verification successful",
                    description=f"Verified content of {fpath}.",
                    agent=qa.name,
                    success=True,
                    metadata={"path": fpath, "preview": str(content)[:200]},
                )
                execution_history.append({
                    "step": "verification",
                    "agent": qa.name,
                    "verified_file": fpath,
                    "content": content,
                })
            except Exception as v_err:
                await agent_runtime.verify(
                    title="File verification failed",
                    description=f"Failed to verify {fpath}: {v_err}",
                    agent=qa.name,
                    success=False,
                )

        await qa.complete("Verification process complete.")

    # Final Response Generation
    await agent_runtime.emit(
        event_type="thinking",
        title="Generating final response",
        description="Synthesizing verified results with NVIDIA Nemotron.",
        status="running",
    )

    final_prompt = f"""
You are FRIDAY.
The user asked: {message}

Execution History & Verified Tool Results:
{json.dumps(execution_history, indent=2, default=str)}

Formulate a clear, helpful, and concise response to the user based strictly on the execution results above.
"""

    final_response = await call_nvidia(final_prompt)

    await agent_runtime.emit(
        event_type="thinking",
        title="Response ready",
        description="Final response generated.",
        status="completed",
    )

    memory_store.add_message("assistant", final_response)
    return final_response
