from __future__ import annotations

import asyncio
from typing import Any

from core.events import FridayEvent
from services.event_bus.bus import event_bus


class AgentRuntime:
    def __init__(self):
        self.agents: dict[str, dict[str, Any]] = {}

    # ==========================================================
    # EVENT EMITTER
    # ==========================================================

    async def emit(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        event = FridayEvent(
            type=event_type,
            title=title,
            description=description,
            agent=agent,
            tool=tool,
            status=status,
            metadata=metadata or {},
        )

        print(
            f"[EVENT BUS] {event_type}: {title}"
        )

        await event_bus.publish(event)

    # ==========================================================
    # CREATE AGENT
    # ==========================================================

    async def create_agent(
        self,
        name: str,
        description: str,
    ):
        self.agents[name] = {
            "name": name,
            "description": description,
        }

        await self.emit(
            event_type="agent_created",
            title=f"{name} created",
            description=description,
            agent=name,
            status="pending",
        )

    # ==========================================================
    # START AGENT
    # ==========================================================

    async def start_agent(
        self,
        name: str,
        description: str | None = None,
    ):
        await self.emit(
            event_type="agent_started",
            title=f"{name} started",
            description=(
                description
                or self.agents.get(name, {}).get(
                    "description",
                    "Agent started.",
                )
            ),
            agent=name,
            status="running",
        )

    # ==========================================================
    # COMPLETE AGENT
    # ==========================================================

    async def complete_agent(
        self,
        name: str,
        description: str = "Agent finished its assigned task.",
        metadata: dict[str, Any] | None = None,
    ):
        await self.emit(
            event_type="agent_completed",
            title=f"{name} completed",
            description=description,
            agent=name,
            status="completed",
            metadata=metadata,
        )

    # ==========================================================
    # START TOOL
    # ==========================================================

    async def start_tool(
        self,
        agent: str,
        tool: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        await self.emit(
            event_type="tool_started",
            title=f"{tool} started",
            description=(
                description
                or f"{agent} is using {tool}."
            ),
            agent=agent,
            tool=tool,
            status="running",
            metadata=metadata,
        )

    # ==========================================================
    # COMPLETE TOOL
    # ==========================================================

    async def complete_tool(
        self,
        agent: str,
        tool: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        await self.emit(
            event_type="tool_completed",
            title=f"{tool} completed",
            description=(
                description
                or f"{tool} completed successfully."
            ),
            agent=agent,
            tool=tool,
            status="completed",
            metadata=metadata,
        )

    # ==========================================================
    # TOOL ERROR
    # ==========================================================

    async def tool_error(
        self,
        agent: str,
        tool: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ):
        await self.emit(
            event_type="tool_error",
            title=f"{tool} failed",
            description=description,
            agent=agent,
            tool=tool,
            status="failed",
            metadata=metadata,
        )

    # ==========================================================
    # VERIFICATION
    # ==========================================================

    async def verify(
        self,
        title: str,
        description: str,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
    ):
        await self.emit(
            event_type="verification",
            title=title,
            description=description,
            agent=agent,
            status=(
                "success"
                if success
                else "failed"
            ),
            metadata=metadata,
        )

    # ==========================================================
    # DEMO / CURRENT WORKFLOW
    #
    # This keeps compatibility with the current orchestrator.
    # Later we will replace this with the real planner/tool
    # execution graph.
    # ==========================================================

    async def run_demo_workflow(
        self,
        user_request: str,
    ):
        # ------------------------------------------------------
        # UNDERSTANDING
        # ------------------------------------------------------

        await self.emit(
            event_type="thinking",
            title="Understanding request",
            description=user_request,
            status="running",
        )

        await asyncio.sleep(0.15)

        await self.emit(
            event_type="thinking",
            title="Request understood",
            description=(
                "The request has been classified."
            ),
            status="completed",
        )

        # ------------------------------------------------------
        # PLANNING
        # ------------------------------------------------------

        await self.emit(
            event_type="planning",
            title="Creating execution plan",
            description=(
                "Breaking the request into independent subtasks."
            ),
            status="running",
        )

        await asyncio.sleep(0.15)

        await self.emit(
            event_type="planning",
            title="Execution plan created",
            description="4 subtasks identified.",
            status="completed",
            metadata={
                "subtasks": 4,
            },
        )

        # ------------------------------------------------------
        # CREATE AGENTS
        # ------------------------------------------------------

        await self.create_agent(
            "Planner Agent",
            "Create and coordinate the execution plan.",
        )

        await self.create_agent(
            "Developer Agent",
            "Inspect the project and identify implementation changes.",
        )

        await self.create_agent(
            "Research Agent",
            "Analyze architecture and identify relevant patterns.",
        )

        await self.create_agent(
            "QA Agent",
            "Verify the proposed implementation.",
        )

        # ------------------------------------------------------
        # PLANNER
        # ------------------------------------------------------

        await self.start_agent(
            "Planner Agent"
        )

        await asyncio.sleep(0.15)

        await self.complete_agent(
            "Planner Agent"
        )

        # ------------------------------------------------------
        # DEVELOPER
        # ------------------------------------------------------

        await self.start_agent(
            "Developer Agent"
        )

        # ------------------------------------------------------
        # TOOL EXAMPLE
        # ------------------------------------------------------

        await self.start_tool(
            agent="Developer Agent",
            tool="filesystem.search",
            description=(
                "Searching the project for relevant files."
            ),
        )

        await asyncio.sleep(0.15)

        await self.complete_tool(
            agent="Developer Agent",
            tool="filesystem.search",
            description=(
                "Filesystem search completed."
            ),
            metadata={
                "simulated": True,
            },
        )

        # ------------------------------------------------------
        # RESEARCH
        # ------------------------------------------------------

        await self.start_agent(
            "Research Agent"
        )

        await asyncio.sleep(0.15)

        await self.complete_agent(
            "Research Agent"
        )

        # ------------------------------------------------------
        # QA
        # ------------------------------------------------------

        await self.start_agent(
            "QA Agent"
        )

        await asyncio.sleep(0.15)

        await self.complete_agent(
            "QA Agent"
        )

        # ------------------------------------------------------
        # DEVELOPER COMPLETE
        # ------------------------------------------------------

        await self.complete_agent(
            "Developer Agent"
        )

        # ------------------------------------------------------
        # VERIFICATION
        # ------------------------------------------------------

        await self.verify(
            title="Execution verified",
            description=(
                "The execution workflow completed successfully."
            ),
            success=True,
        )

agent_runtime = AgentRuntime()