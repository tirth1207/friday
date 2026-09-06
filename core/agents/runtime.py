from __future__ import annotations

from typing import Any
from core.events import FridayEvent
from services.event_bus.bus import event_bus


class AgentRuntime:
    def __init__(self):
        self.agents: dict[str, dict[str, Any]] = {}

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
        await event_bus.publish(event)

    async def create_agent(self, name: str, description: str):
        self.agents[name] = {"name": name, "description": description}
        await self.emit(
            event_type="agent_created",
            title=f"{name} created",
            description=description,
            agent=name,
            status="pending",
        )

    async def start_agent(self, name: str, description: str | None = None):
        await self.emit(
            event_type="agent_started",
            title=f"{name} started",
            description=description or self.agents.get(name, {}).get("description", "Agent started."),
            agent=name,
            status="running",
        )

    async def complete_agent(self, name: str, description: str = "Agent finished its assigned task.", metadata: dict[str, Any] | None = None):
        await self.emit(
            event_type="agent_completed",
            title=f"{name} completed",
            description=description,
            agent=name,
            status="completed",
            metadata=metadata,
        )

    async def start_tool(self, agent: str, tool: str, description: str | None = None, metadata: dict[str, Any] | None = None):
        await self.emit(
            event_type="tool_started",
            title=f"{tool} started",
            description=description or f"{agent} is using {tool}.",
            agent=agent,
            tool=tool,
            status="running",
            metadata=metadata,
        )

    async def complete_tool(self, agent: str, tool: str, description: str | None = None, metadata: dict[str, Any] | None = None):
        await self.emit(
            event_type="tool_completed",
            title=f"{tool} completed",
            description=description or f"{tool} completed successfully.",
            agent=agent,
            tool=tool,
            status="completed",
            metadata=metadata,
        )

    async def tool_error(self, agent: str, tool: str, description: str, metadata: dict[str, Any] | None = None):
        await self.emit(
            event_type="tool_error",
            title=f"{tool} failed",
            description=description,
            agent=agent,
            tool=tool,
            status="failed",
            metadata=metadata,
        )

    async def verify(self, title: str, description: str, agent: str | None = None, metadata: dict[str, Any] | None = None, success: bool = True):
        await self.emit(
            event_type="verification",
            title=title,
            description=description,
            agent=agent,
            status="success" if success else "failed",
            metadata=metadata,
        )


agent_runtime = AgentRuntime()
