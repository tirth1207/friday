from typing import Any
from core.agents.runtime import agent_runtime


class BaseAgent:
    def __init__(self, name: str, role: str, description: str):
        self.name = name
        self.role = role
        self.description = description

    async def create(self):
        await agent_runtime.create_agent(self.name, self.description)

    async def start(self, task_description: str | None = None):
        await agent_runtime.start_agent(self.name, task_description)

    async def complete(
        self, description: str = "Task completed.", metadata: dict[str, Any] | None = None
    ):
        await agent_runtime.complete_agent(self.name, description, metadata)


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Planner Agent",
            role="Planner",
            description="Analyzes request and coordinates plan execution.",
        )


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Developer Agent",
            role="Developer",
            description="Inspects code, executes filesystem operations, and modifies code.",
        )


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Research Agent",
            role="Research",
            description="Inspects project architecture and documentation.",
        )


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="QA Agent",
            role="QA",
            description="Verifies execution output and validates results.",
        )
