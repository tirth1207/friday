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
            description="Understands the request, creates the execution plan, and delegates work to specialist agents.",
        )


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Developer Agent",
            role="Developer",
            description="Inspects code, runs development commands, and performs approved code changes.",
        )


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Research Agent",
            role="Research",
            description="Inspects documentation, architecture, external information, and project context.",
        )


class GitHubAgent(BaseAgent):
    """GitHub specialist backed by deterministic GitHub tools."""

    def __init__(self):
        super().__init__(
            name="GitHub Agent",
            role="GitHub Research",
            description="Fetches and understands public and authenticated private GitHub repositories without exposing credentials.",
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
                "You are FRIDAY's GitHub Agent. Use only supplied GitHub tools. "
                "Inspect repositories from evidence, never reveal credentials, and clearly identify missing data."
            ),
            name="github_agent",
        )


class OSAgent(BaseAgent):
    """Local operating-system inspection specialist."""

    def __init__(self):
        super().__init__(
            name="OS Agent",
            role="OS Operations",
            description="Inspects safe operating-system state, drives, processes, and local paths.",
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
                "You are FRIDAY's OS Agent. Use only safe OS inspection tools. "
                "Never expose environment variables or credentials and never execute arbitrary commands."
            ),
            name="os_agent",
        )


class SelfImprovementAgent(BaseAgent):
    """Controlled specialist for improving FRIDAY itself."""

    def __init__(self):
        super().__init__(
            name="Self-Improvement Agent",
            role="FRIDAY Engineering",
            description=(
                "Inspects FRIDAY's own codebase, tests behavior, diagnoses failures, proposes improvements, "
                "and performs only explicitly approved mutations."
            ),
        )

    def allowed_tools(self) -> tuple[str, ...]:
        return (
            "filesystem.list",
            "filesystem.search",
            "filesystem.read",
            "filesystem.write",
            "filesystem.create",
            "filesystem.exists",
            "git.status",
            "git.diff",
            "git.log",
            "git.branch",
            "terminal.execute",
        )

    def policy(self) -> str:
        return (
            "SELF-IMPROVEMENT POLICY: First inspect the actual FRIDAY code and tests. "
            "Then diagnose and propose a minimal change. Run verification before claiming success. "
            "Writes, deletes, dependency changes, commits, pushes, and deployment require explicit user approval. "
            "Never modify secrets or bypass permission checks. Never silently rewrite the supervisor, permissions, or audit trail."
        )


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="QA Agent",
            role="QA",
            description="Verifies execution results, runs tests, and checks that requested changes actually work.",
        )
