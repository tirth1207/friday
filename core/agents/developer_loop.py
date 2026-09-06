"""Goal-driven developer loop for FRIDAY.

Turns a software goal into inspect -> plan -> implement -> verify -> repair -> learn.
All mutations continue through the permission-gated ToolExecutor.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from core.agents.runtime import agent_runtime
from core.memory import memory_store
from core.runtime.executor import tool_executor
from core.runtime.langchain_tools import get_langchain_tools, serialize_tool_result
from providers.nvidia.client import get_model

LOOP_PROMPT = """You are FRIDAY's Developer Agent.
Operate as an engineering loop: inspect -> plan -> implement -> verify -> repair -> finish.
Inspect before changing anything. Prefer the smallest coherent implementation.
Use tools for real evidence. Never invent file contents or test results.
After implementation, run appropriate project tests/build/lint commands when available.
If verification fails, diagnose and repair within the bounded iteration limit.
Never expose private reasoning. Return only the final engineering summary.
All mutating operations must go through FRIDAY's permission-gated executor.
Do not call developer.run from inside this loop; use the concrete workspace, git, filesystem and terminal tools.
"""


class DeveloperLoop:
    def __init__(self, max_iterations: int = 4, allow_mutations: bool = False):
        self.max_iterations = max(1, min(max_iterations, 8))
        self.allow_mutations = allow_mutations

    async def _tool(self, name: str, args: dict[str, Any], history: list[dict[str, Any]]) -> Any:
        result = await tool_executor.execute(name, args, agent="Developer Agent", confirmed=self.allow_mutations)
        history.append({"tool": name, "arguments": args, "result": result})
        return result

    async def _drive(self, model, messages: list[Any], history: list[dict[str, Any]], rounds: int = 4) -> str:
        final_text = ""
        for _ in range(rounds):
            response = await model.ainvoke(messages)
            messages.append(response)
            calls = list(getattr(response, "tool_calls", []) or [])
            if not calls:
                final_text = str(getattr(response, "content", ""))
                break
            for call in calls:
                name = str(call.get("name", ""))
                args = call.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                if name in {"developer__run", "developer.run"}:
                    history.append({"tool": name, "error": "Recursive developer.run call blocked."})
                    messages.append(ToolMessage(content="Recursive developer.run is unavailable inside the developer loop. Use concrete tools instead.", tool_call_id=call.get("id") or name))
                    continue
                try:
                    result = await self._tool(name, args, history)
                    messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=call.get("id") or name))
                except Exception as error:
                    history.append({"tool": name, "arguments": args, "error": str(error)})
                    messages.append(ToolMessage(content=f"Tool failed: {error}", tool_call_id=call.get("id") or name))
        return final_text

    async def run(self, goal: str, repository: str | None = None) -> dict[str, Any]:
        agent = "Developer Agent"
        await agent_runtime.create_agent(agent, "Goal-driven inspect, implement, verify and repair loop.")
        await agent_runtime.start_agent(agent, f"Working on: {goal[:160]}")
        history: list[dict[str, Any]] = []
        state: dict[str, Any] = {"goal": goal, "repository": repository, "iteration": 0, "verified": False}

        await agent_runtime.emit("planning", "Developer loop plan", "Preparing an inspect → implement → verify cycle.", agent=agent, status="running")
        await self._tool("filesystem.list", {"path": "."}, history)
        await self._tool("git.status", {}, history)

        tools = [tool for tool in get_langchain_tools() if tool.name not in {"developer__run", "developer.run"}]
        model = get_model(require_tools=True).bind_tools(tools)
        messages: list[Any] = [
            SystemMessage(content=LOOP_PROMPT),
            HumanMessage(content=json.dumps({
                "goal": goal,
                "repository": repository,
                "phase": "inspect_and_plan",
                "instruction": "Inspect the workspace and relevant files, then prepare the implementation plan. Do not mutate during this phase.",
            }, ensure_ascii=False)),
        ]
        plan_summary = await self._drive(model, messages, history, rounds=3)
        await agent_runtime.emit("planning", "Implementation plan ready", "Inspection evidence is available; beginning implementation work.", agent=agent, status="completed")

        for iteration in range(1, self.max_iterations + 1):
            state["iteration"] = iteration
            await agent_runtime.emit("verification", f"Engineering iteration {iteration}", "Implementing and verifying against the requested goal.", agent=agent, status="running")
            messages.append(HumanMessage(content=json.dumps({
                "goal": goal,
                "repository": repository,
                "phase": "implement_and_verify",
                "iteration": iteration,
                "mutations_enabled": self.allow_mutations,
                "instruction": "Implement the next required change using concrete tools. Run appropriate verification. If verification fails, repair it. If mutations are disabled, report the exact proposed changes instead of attempting writes.",
            }, ensure_ascii=False)))
            final_text = await self._drive(model, messages, history, rounds=4)
            state["last_model_summary"] = final_text[:3000]
            if any(word in final_text.lower() for word in ("verified", "tests pass", "successfully completed", "goal is complete")):
                state["verified"] = True
                await agent_runtime.emit("verification", f"Iteration {iteration} verified", "The developer agent reports the goal is satisfied.", agent=agent, status="completed")
                break
            await agent_runtime.emit("verification", f"Iteration {iteration} completed", "The goal is not yet verified; continuing within the bounded loop.", agent=agent, status="completed")

        summary = {
            "goal": goal,
            "repository": repository,
            "iterations": state["iteration"],
            "verified": state["verified"],
            "mutations_enabled": self.allow_mutations,
            "plan_summary": plan_summary[:2000],
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
