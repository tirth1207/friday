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
        super().__init__("Research Agent", "Research", "Researches the public web and structured OSIRIS feeds, fetches source pages, and synthesizes evidence.")

    def tools(self):
        from tools.research.web_fetch import web_fetch
        from tools.research.web_search import web_search
        from tools.osiris.osiris_tools import osiris_news, osiris_live_news
        from tools.osiris.intelligence_router import osiris_intelligence_brief
        return [web_search, web_fetch, osiris_intelligence_brief, osiris_news, osiris_live_news]

    def build_langchain_agent(self):
        from langchain.agents import create_agent
        from providers.nvidia.client import get_model
        return create_agent(model=get_model(), tools=self.tools(), system_prompt="You are FRIDAY's Research Agent. Search broadly when needed, fetch primary pages, distinguish evidence from inference, and cite source URLs in your final synthesis.", name="research_agent")


class BrowserAgent(BaseAgent):
    def __init__(self):
        super().__init__("Browser Agent", "Browser Automation", "Navigates stateful headless browser sessions and reads/interacts with webpages under permission controls.")

    def tools(self):
        from tools.browser.browser_tools import BROWSER_LANGCHAIN_TOOLS
        return BROWSER_LANGCHAIN_TOOLS

    def allowed_tools(self) -> tuple[str, ...]:
        return ("browser.navigate", "browser.read_page", "browser.click", "browser.type", "browser.screenshot", "browser.close")


class MusicAgent(BaseAgent):
    def __init__(self):
        super().__init__("Music Agent", "Music Control", "Controls Spotify playback and reports the current track when the user's Spotify integration is configured.")

    def tools(self):
        from tools.music.music_tools import MUSIC_LANGCHAIN_TOOLS
        return MUSIC_LANGCHAIN_TOOLS


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
        super().__init__("Cognition Agent", "Learning & Curiosity", "Maintains reusable experiences, recalls prior lessons, and maintains explicit user profile memory.")

    def allowed_tools(self) -> tuple[str, ...]:
        return ("cognition.learn", "cognition.recall", "cognition.curiosity", "cognition.checkpoint", "memory.remember", "memory.recall")
