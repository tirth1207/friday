"""Goal-driven developer loop for FRIDAY.

The loop turns a software goal into inspect -> plan -> implement -> verify -> repair -> learn.
It deliberately uses the existing permission-gated tool executor instead of bypassing runtime policy.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.agents.runtime import agent_runtime
from core.memory import memory_store
from core.runtime.executor import tool_executor
from core.runtime.langchain_tools import get_langchain_tools, serialize_tool_result
from providers.nvidia.client import get_model


LOOP_PROMPT = """You are FRIDAY's Developer Agent.
You are operating an engineering loop, not merely answering a question.
Inspect before changing anything. Prefer the smallest coherent implementation.
Use available tools for real evidence. Never invent file contents or test results.
After implementation, verify with the project's existing test/build/lint commands when available.
If verification fails, diagnose and repair, bounded by the supplied iteration limit.
Never expose private reasoning. Return only concise action plans, tool decisions, or final engineering summaries.
Mutating tools remain permission-gated by the runtime; never bypass those checks.
"""


class DeveloperLoop:
    def __init__(self, max_iterations: int = 4):
        self.max_iterations = max(1, min(max_iterations, 8))

    async def _tool(self, name: str, args: dict[str, Any], history: list[dict[str, Any]]) -> Any:
        result = await tool_executor.execute(name, args, agent="Developer Agent")
        history.append({"tool": name, "arguments": args, "result": result})
        return result

    async def run(self, goal: str, repository: str | None = None) -> dict[str, Any]:
        agent = "Developer Agent"
        await agent_runtime.create_agent(agent, "Goal-driven inspect, implement, verify and repair loop.")
        await agent_runtime.start_agent(agent, f"Working on: {goal[:160]}")
        history: list[dict[str, Any]] = []
        state: dict[str, Any] = {"goal": goal, "repository": repository, "iteration": 0, "verified": False}

        await agent_runtime.emit("planning", "Developer loop plan", "Preparing an inspect → implement → verify cycle.", agent=agent, status="running")

        # First pass: establish workspace and Git state.
        await self._tool("filesystem.list", {"path": "."}, history)
        await self._tool("git.status", {}, history)

        tools = get_langchain_tools()
        model = get_model(require_tools=True).bind_tools(tools)
        messages: list[Any] = [
            SystemMessage(content=LOOP_PROMPT),
            HumanMessage(content=json.dumps({
                "goal": goal,
                "repository": repository,
                "phase": "inspect_and_plan",
                "instruction": "Use tools to inspect the workspace, identify relevant files, and form an implementation plan. Do not mutate yet.",
            }, ensure_ascii=False)),
        ]

        # Planning/inspection phase is model-driven and evidence-backed.
        for _ in range(3):
            response = await model.ainvoke(messages)
            messages.append(response)
            calls = list(getattr(response, "tool_calls", []) or [])
            if not calls:
                break
            for call in calls:
                name = str(call.get("name", ""))
                args = call.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                result = await self._tool(name, args, history)
                messages.append({"role": "tool", "content": serialize_tool_result(result), "tool_call_id": call.get("id", name)})

        await agent_runtime.emit("planning", "Implementation plan ready", "Inspection evidence is available; beginning approved implementation work.", agent=agent, status="completed")

        for iteration in range(1, self.max_iterations + 1):
            state["iteration"] = iteration
            await agent_runtime.emit("verification", f"Engineering iteration {iteration}", "Implementing and verifying against the requested goal.", agent=agent, status="running")
            messages.append(HumanMessage(content=json.dumps({
                "goal": goal,
                "repository": repository,
                "phase": "implement_and_verify",
                "iteration": iteration,
                "instruction": "Implement the next required change using tools. Then run appropriate verification. If verification fails, fix it in the next cycle. Stop when the goal is genuinely satisfied.",
            }, ensure_ascii=False)))
            response = await model.ainvoke(messages)
            messages.append(response)
            calls = list(getattr(response, "tool_calls", []) or [])
            if not calls:
                text = str(getattr(response, "content", ""))
                state["last_model_summary"] = text[:2000]
                if "verified" in text.lower() or "complete" in text.lower():
                    state["verified"] = True
                    break
                continue
            for call in calls:
                name = str(call.get("name", ""))
                args = call.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                try:
                    result = await self._tool(name, args, history)
                    messages.append({"role": "tool", "content": serialize_tool_result(result), "tool_call_id": call.get("id", name)})
                except Exception as error:
                    history.append({"tool": name, "arguments": args, "error": str(error)})
                    messages.append({"role": "tool", "content": f"Tool failed: {error}", "tool_call_id": call.get("id", name)})
            await agent_runtime.emit("verification", f"Iteration {iteration} completed", "Tool execution finished; checking whether the goal is satisfied.", agent=agent, status="completed")

        summary = {
            "goal": goal,
            "repository": repository,
            "iterations": state["iteration"],
            "verified": state["verified"],
            "history": history[-40:],
            "summary": state.get("last_model_summary", "Developer loop completed its bounded execution window."),
        }
        memory_store.add_experience({
            "kind": "engineering_run",
            "title": f"Developer loop: {goal[:100]}",
            "lesson": "Recorded an inspect/implement/verify engineering run for future retrieval.",
            "context": json.dumps({"repository": repository, "iterations": state["iteration"], "verified": state["verified"]}, ensure_ascii=False),
        })
        await agent_runtime.complete_agent(agent, "Developer execution loop finished.", metadata={"verified": state["verified"], "iterations": state["iteration"]})
        return summary
