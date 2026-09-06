"""Bounded inspect -> implement -> verify -> learn developer loop."""
from __future__ import annotations
import json
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from core.agents.runtime import agent_runtime
from core.memory import memory_store
from core.runtime.executor import tool_executor
from core.runtime.langchain_tools import get_langchain_tools, registry_tool_name, serialize_tool_result
from core.runtime.workspace import scoped_workspace
from providers.nvidia.client import get_model
from tools.git.workspace import prepare_repository_workspace

LOOP_PROMPT = """You are FRIDAY's Developer Agent. Operate as inspect -> plan -> implement -> verify -> repair -> finish.
For a selected GitHub repository, all filesystem, Git and terminal tools operate inside an isolated local clone.
Inspect before changing anything. Use real tool evidence. Never invent file contents or test results.
Run appropriate project tests/build/lint after changes. Repair failures within the bounded iteration limit.
Never expose private reasoning. Return only the final engineering summary.
All mutations use FRIDAY's permission-gated executor. Never call developer.run recursively.
Provider-safe names containing `__` map to dotted registry names, e.g. `github__analyze` -> `github.analyze`.
Verification requires concrete successful tool evidence; model wording alone is never verification."""

class DeveloperLoop:
    def __init__(self, max_iterations: int = 4, allow_mutations: bool = False):
        self.max_iterations = max(1, min(max_iterations, 8))
        self.allow_mutations = allow_mutations
        self.execution_workspace: str | None = None

    async def _tool(self, name: str, args: dict[str, Any], history: list[dict[str, Any]]) -> Any:
        registry_name = registry_tool_name(name)
        if self.execution_workspace:
            with scoped_workspace(self.execution_workspace):
                result = await tool_executor.execute(registry_name, args, agent="Developer Agent", confirmed=self.allow_mutations)
        else:
            result = await tool_executor.execute(registry_name, args, agent="Developer Agent", confirmed=self.allow_mutations)
        history.append({"tool": registry_name, "model_tool": name, "arguments": args, "result": result})
        return result

    @staticmethod
    def _verification_evidence(history: list[dict[str, Any]]) -> bool:
        for entry in reversed(history):
            if entry.get("tool") != "terminal.execute" or "error" in entry:
                continue
            result = entry.get("result")
            if isinstance(result, dict) and result.get("exit_code") == 0:
                return True
            text = json.dumps(result, ensure_ascii=False, default=str).lower()
            if any(x in text for x in ("exit code: 0", '"returncode": 0', '"return_code": 0', "tests passed", "all tests passed")):
                return True
        return False

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
                model_name = str(call.get("name", ""))
                args = call.get("args") or {}
                if not isinstance(args, dict): args = {}
                registry_name = registry_tool_name(model_name)
                if registry_name == "developer.run":
                    history.append({"tool": registry_name, "error": "Recursive developer.run blocked."})
                    messages.append(ToolMessage(content="Recursive developer.run is unavailable here.", tool_call_id=call.get("id") or model_name))
                    continue
                try:
                    result = await self._tool(model_name, args, history)
                    messages.append(ToolMessage(content=serialize_tool_result(result), tool_call_id=call.get("id") or model_name))
                except Exception as error:
                    history.append({"tool": registry_name, "arguments": args, "error": str(error)})
                    messages.append(ToolMessage(content=f"Tool failed: {error}", tool_call_id=call.get("id") or model_name))
        return final_text

    async def run(self, goal: str, repository: str | None = None) -> dict[str, Any]:
        agent = "Developer Agent"
        await agent_runtime.create_agent(agent, "Goal-driven inspect, implement, verify and repair loop.")
        await agent_runtime.start_agent(agent, f"Working on: {goal[:160]}")
        history: list[dict[str, Any]] = []
        state = {"goal": goal, "repository": repository, "iteration": 0, "verified": False}

        if repository:
            await agent_runtime.emit("planning", "Preparing repository workspace", f"Preparing an isolated workspace for {repository}.", agent=agent, status="running")
            if not self.allow_mutations:
                raise PermissionError("Repository execution requires mutation permission.")
            prepared = await prepare_repository_workspace(repository)
            self.execution_workspace = str(prepared["workspace"])
            state["execution_workspace"] = self.execution_workspace
            await agent_runtime.emit("planning", "Repository workspace ready", "Developer tools are scoped to the isolated repository clone.", agent=agent, status="completed")

        await agent_runtime.emit("planning", "Developer loop plan", "Preparing inspect -> implement -> verify cycle.", agent=agent, status="running")
        await self._tool("filesystem.list", {"path": "."}, history)
        await self._tool("git.status", {}, history)
        tools = [t for t in get_langchain_tools() if t.name not in {"developer__run", "developer.run", "git__workspace__prepare"}]
        model = get_model(require_tools=True).bind_tools(tools)
        messages: list[Any] = [SystemMessage(content=LOOP_PROMPT), HumanMessage(content=json.dumps({"goal": goal, "repository": repository, "execution_workspace": self.execution_workspace, "phase": "inspect_and_plan"}, ensure_ascii=False))]
        plan_summary = await self._drive(model, messages, history, rounds=3)
        await agent_runtime.emit("planning", "Implementation plan ready", "Inspection evidence is available; beginning implementation.", agent=agent, status="completed")

        for iteration in range(1, self.max_iterations + 1):
            state["iteration"] = iteration
            await agent_runtime.emit("verification", f"Engineering iteration {iteration}", "Implementing and verifying against the goal.", agent=agent, status="running")
            messages.append(HumanMessage(content=json.dumps({"goal": goal, "repository": repository, "execution_workspace": self.execution_workspace, "phase": "implement_and_verify", "iteration": iteration, "mutations_enabled": self.allow_mutations}, ensure_ascii=False)))
            final_text = await self._drive(model, messages, history, rounds=4)
            state["last_model_summary"] = final_text[:3000]
            if self._verification_evidence(history):
                state["verified"] = True
                await agent_runtime.emit("verification", f"Iteration {iteration} verified", "A concrete verification command completed successfully.", agent=agent, status="completed")
                break
            await agent_runtime.emit("verification", f"Iteration {iteration} completed", "No concrete verification success observed; continuing.", agent=agent, status="completed")

        result = {"goal": goal, "repository": repository, "execution_workspace": self.execution_workspace, "iterations": state["iteration"], "verified": state["verified"], "mutations_enabled": self.allow_mutations, "plan_summary": plan_summary[:2000], "history": history[-40:], "summary": state.get("last_model_summary", "Developer loop completed its bounded execution window.")}
        memory_store.add_experience({"kind": "engineering_run", "title": f"Developer loop: {goal[:100]}", "lesson": "Recorded an inspect/implement/verify engineering run in an isolated repository workspace.", "context": json.dumps({"repository": repository, "workspace": self.execution_workspace, "iterations": state["iteration"], "verified": state["verified"]}, ensure_ascii=False)})
        await agent_runtime.complete_agent(agent, "Developer execution loop finished.", metadata={"verified": state["verified"], "iterations": state["iteration"], "repository_workspace": bool(self.execution_workspace)})
        return result
