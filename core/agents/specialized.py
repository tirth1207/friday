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


class GitHubAgent(BaseAgent):
    """GitHub specialist backed by LangChain tools and the GitHub REST API."""

    def __init__(self):
        super().__init__(
            name="GitHub Agent",
            role="GitHub Research",
            description="Fetches authenticated GitHub profile, repository, and commit data without exposing credentials.",
        )

    def tools(self):
        from tools.github.github_tools import GITHUB_LANGCHAIN_TOOLS

        return GITHUB_LANGCHAIN_TOOLS

    def build_langchain_agent(self):
        from langchain.agents import create_agent
        from providers.nvidia.client import get_model

        return create_agent(
            model=get_model(),
            tools=self.tools(),
            system_prompt=(
                "You are FRIDAY's GitHub Agent. Use only the supplied GitHub tools. "
                "Never reveal, repeat, log, or infer the GitHub PAT. "
                "Base answers on tool results and clearly distinguish missing data from facts."
            ),
            name="github_agent",
        )


class OSAgent(BaseAgent):
    """Local OS inspection specialist backed by LangChain tools."""

    def __init__(self):
        super().__init__(
            name="OS Agent",
            role="OS Operations",
            description="Inspects safe operating-system state such as host information, processes, disk usage, and working directory.",
        )

    def tools(self):
        from tools.os.os_tools import OS_LANGCHAIN_TOOLS

        return OS_LANGCHAIN_TOOLS

    def build_langchain_agent(self):
        from langchain.agents import create_agent
        from providers.nvidia.client import get_model

        return create_agent(
            model=get_model(),
            tools=self.tools(),
            system_prompt=(
                "You are FRIDAY's OS Agent. Use only the supplied safe inspection tools. "
                "Never expose environment variables or credentials. Do not execute arbitrary commands; "
                "command execution belongs to FRIDAY's separately permissioned terminal tool."
            ),
            name="os_agent",
        )


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="QA Agent",
            role="QA",
            description="Verifies execution output and validates results.",
        )
