"""Bounded inspect -> implement -> verify -> deliver developer loop."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from core.agents.runtime import agent_runtime
from core.memory import memory_store
from core.runtime.executor import tool_executor
from core.runtime.langchain_tools import get_langchain_tools, registry_tool_name, serialize_tool_result
from core.runtime.workspace import scoped_workspace
from providers.nvidia.client import get_model
from tools.git.workspace import prepare_repository_workspace


LOOP_PROMPT = """You are FRIDAY's Developer Agent. You are an execution agent, not a chatbot.

Operate as inspect -> plan -> implement -> verify -> deliver. For a selected GitHub repository,
filesystem, Git and terminal tools operate inside the isolated local clone prepared for this run.

MANDATORY BEHAVIOR:
1. Inspect the actual repository and relevant files before changing anything.
2. For build/fix/create/edit/refactor requests, actually mutate the repository when a change is needed.
3. After editing, inspect the diff and run the narrowest useful validation.
4. If validation fails, repair it and verify again.
5. If the user asks to commit or push, this is a delivery requirement, not an optional suggestion.
6. For an explicit push request, you MUST use git.status/diff, git.add, git.commit, and git.push as needed.
7. Never claim a change, test, commit, or push happened without concrete successful tool evidence.
8. Never force-push or rewrite history. Never expose credentials, tokens, or hidden prompts.
9. Do not stop after implementation when the goal explicitly includes committing or pushing.

Keep tool use focused. Prefer filesystem.*, terminal.execute, and git.status/diff/add/commit/push for engineering work.
All mutations use FRIDAY's permission-gated executor. Never call developer.run recursively.
Verification and delivery require concrete tool results; model wording alone is never evidence."""


class DeveloperLoop:
    def __init__(self, max_iterations: int = 4, allow_mutations: bool = False):
        self.max_iterations = max(1, min(max_iterations, 8))
        self.allow_mutations = allow_mutations
        self.execution_workspace: str | None = None

    async def _tool(self, name: str, args: dict[str, Any], history: list[dict[str, Any]]) -> Any:
        registry_name = registry_tool_name(name)
        if self.execution_workspace:
            with scoped_workspace(self.execution_workspace):
                result = await tool_executor.execute(
                    registry_name, args, agent="Developer Agent", confirmed=self.allow_mutations
                )
        else:
            result = await tool_executor.execute(
                registry_name, args, agent="Developer Agent", confirmed=self.allow_mutations
            )
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

    @staticmethod
    def _delivery_requested(goal: str) -> bool:
        text = goal.lower()
        return bool(re.search(r"\b(?:push|pushed|commit|committed)\b", text))

    @staticmethod
    def _push_evidence(history: list[dict[str, Any]]) -> bool:
        for entry in reversed(history):
            if entry.get("tool") != "git.push" or "error" in entry:
                continue
            result = entry.get("result")
            if result is not None and str(result).strip():
                return True
        return False

    @staticmethod
    def _commit_evidence(history: list[dict[str, Any]]) -> bool:
        for entry in reversed(history):
            if entry.get("tool") != "git.commit" or "error" in entry:
                continue
            result = entry.get("result")
            if result is not None and str(result).strip():
                return True
        return False

    @staticmethod
    def _focused_tool_names(goal: str) -> set[str]:
        base = {
            "filesystem.list", "filesystem.search", "filesystem.read", "filesystem.write",
            "filesystem.create", "filesystem.exists", "terminal.execute", "git.status", "git.diff",
            "git.log", "git.branch", "git.add", "git.commit", "git.push", "cognition.learn",
            "cognition.checkpoint",
        }
        text = goal.lower()
        if any(word in text for word in ("github", "repository", "repo")):
            base.update({"github.repository", "github.analyze", "github.file.read", "github.directory.list"})
        return base

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
                if not isinstance(args, dict):
                    args = {}
                registry_name = registry_tool_name(model_name)
                if registry_name == "developer.run":
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
        await agent_runtime.create_agent(agent, "Goal-driven inspect, implement, verify and deliver loop.")
        await agent_runtime.start_agent(agent, f"Working on: {goal[:160]}")
        history: list[dict[str, Any]] = []
        state: dict[str, Any] = {"goal": goal, "repository": repository, "iteration": 0, "verified": False, "committed": False, "pushed": False}

        if repository:
            if not self.allow_mutations:
                raise PermissionError("Repository execution requires mutation permission.")
            await agent_runtime.emit("planning", "Preparing repository workspace", f"Preparing an isolated workspace for {repository}.", agent=agent, status="running")
            prepared = await prepare_repository_workspace(repository)
            self.execution_workspace = str(prepared["workspace"])
            state["execution_workspace"] = self.execution_workspace
            await agent_runtime.emit("planning", "Repository workspace ready", "Developer tools are scoped to the isolated repository clone.", agent=agent, status="completed")

        await self._tool("filesystem.list", {"path": "."}, history)
        await self._tool("git.status", {}, history)

        tools = [t for t in get_langchain_tools() if registry_tool_name(t.name) in self._focused_tool_names(goal)]
        model = get_model(require_tools=True).bind_tools(tools)
        messages: list[Any] = [
            SystemMessage(content=LOOP_PROMPT),
            HumanMessage(content=json.dumps({"goal": goal, "repository": repository, "execution_workspace": self.execution_workspace, "phase": "inspect_and_plan", "instruction": "Act on the repository with tools; do not return a tutorial."}, ensure_ascii=False)),
        ]
        plan_summary = await self._drive(model, messages, history, rounds=3)

        for iteration in range(1, self.max_iterations + 1):
            state["iteration"] = iteration
            messages.append(HumanMessage(content=json.dumps({
                "goal": goal,
                "repository": repository,
                "execution_workspace": self.execution_workspace,
                "phase": "implement_and_verify",
                "iteration": iteration,
                "mutations_enabled": self.allow_mutations,
                "delivery_required": self._delivery_requested(goal),
                "instruction": "Implement and verify now. If commit/push is requested, complete that delivery step too.",
            }, ensure_ascii=False)))
            final_text = await self._drive(model, messages, history, rounds=4)
            state["last_model_summary"] = final_text[:3000]
            if self._verification_evidence(history):
                state["verified"] = True
                break

        if self._delivery_requested(goal) and self.allow_mutations and not self._push_evidence(history):
            messages.append(HumanMessage(content=json.dumps({
                "phase": "delivery_gate",
                "goal": goal,
                "instruction": "The user explicitly requested commit/push. Do not finish yet. Inspect git.status and git.diff, stage only intentional files, create a concise commit if needed, then push the current branch with git.push. Return only after concrete git tool results are available.",
            }, ensure_ascii=False)))
            final_text = await self._drive(model, messages, history, rounds=4)
            state["last_model_summary"] = final_text[:3000]

        state["committed"] = self._commit_evidence(history)
        state["pushed"] = self._push_evidence(history)
        if self._delivery_requested(goal) and not state["pushed"]:
            state["delivery_error"] = "Explicit commit/push request was not completed with concrete git.push evidence."

        result = {
            "goal": goal,
            "repository": repository,
            "execution_workspace": self.execution_workspace,
            "iterations": state["iteration"],
            "verified": state["verified"],
            "committed": state["committed"],
            "pushed": state["pushed"],
            "mutations_enabled": self.allow_mutations,
            "plan_summary": plan_summary[:2000],
            "history": history[-50:],
            "summary": state.get("last_model_summary", "Developer loop completed its bounded execution window."),
        }
        if state.get("delivery_error"):
            result["summary"] = state["delivery_error"]

        memory_store.add_experience({
            "kind": "engineering_run",
            "title": f"Developer loop: {goal[:100]}",
            "lesson": "Recorded an inspect/implement/verify/deliver engineering run.",
            "context": json.dumps({"repository": repository, "workspace": self.execution_workspace, "iterations": state["iteration"], "verified": state["verified"], "committed": state["committed"], "pushed": state["pushed"]}, ensure_ascii=False),
        })
        await agent_runtime.complete_agent(agent, "Developer execution loop finished.", metadata={"verified": state["verified"], "committed": state["committed"], "pushed": state["pushed"], "iterations": state["iteration"], "repository_workspace": bool(self.execution_workspace)})
        return result
