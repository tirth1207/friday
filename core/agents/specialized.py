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

    async def complete(self, description: str = "Task completed.", metadata: dict[str, Any] | None = None):
        await agent_runtime.complete_agent(self.name, description, metadata)


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Planner Agent", "Planner", "Breaks complex goals into verifiable steps and delegates them to specialist agents.")


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__("Developer Agent", "Developer", "Inspects code, designs implementations, runs development commands, and performs approved code changes.")


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("Research Agent", "Research", "Inspects documentation, architecture, external information, and project context.")


class GitHubAgent(BaseAgent):
    def __init__(self):
        super().__init__("GitHub Agent", "GitHub Research", "Fetches and understands accessible public and authenticated private GitHub repositories without exposing credentials.")

    def tools(self):
        from tools.github.github_tools import GITHUB_LANGCHAIN_TOOLS
        return GITHUB_LANGCHAIN_TOOLS

    def build_langchain_agent(self):
        from langchain.agents import create_agent
        from providers.nvidia.client import get_model
        return create_agent(model=get_model(), tools=self.tools(), system_prompt="You are FRIDAY's GitHub Agent. Use only supplied GitHub tools. Inspect from evidence and never reveal credentials.", name="github_agent")


class OSAgent(BaseAgent):
    def __init__(self):
        super().__init__("OS Agent", "OS Operations", "Inspects safe operating-system state and local environment.")

    def tools(self):
        from tools.os.os_tools import OS_LANGCHAIN_TOOLS
        return OS_LANGCHAIN_TOOLS


class SelfImprovementAgent(BaseAgent):
    def __init__(self):
        super().__init__("Self-Improvement Agent", "FRIDAY Engineering", "Inspects FRIDAY, diagnoses failures, proposes improvements, and performs only explicitly approved mutations.")

    def allowed_tools(self) -> tuple[str, ...]:
        return ("filesystem.list", "filesystem.search", "filesystem.read", "filesystem.write", "filesystem.create", "filesystem.exists", "git.status", "git.diff", "git.log", "git.branch", "terminal.execute")

    def policy(self) -> str:
        return "Inspect actual code and tests first. Diagnose, propose a minimal change, then verify. Writes, deletes, dependency changes, commits, pushes, and deployment require explicit user approval. Never modify secrets or bypass permission checks."


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__("QA Agent", "QA", "Verifies execution results, runs tests, and checks that requested changes actually work.")


class CognitionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Cognition Agent", "Learning & Curiosity", "Maintains reusable experiences, recalls prior lessons, creates bounded curiosity probes, and checkpoints long-running goals.")

    def allowed_tools(self) -> tuple[str, ...]:
        return ("cognition.learn", "cognition.recall", "cognition.curiosity", "cognition.checkpoint")
