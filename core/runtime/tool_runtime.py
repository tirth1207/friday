from core.events import FridayEvent
from services.event_bus.bus import event_bus
from core.runtime.executor import tool_executor


class ToolRuntime:
    async def emit(self, event_type, title, description=None, agent=None, tool=None, status=None, metadata=None):
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

    async def execute(self, tool_name: str, agent: str, confirmed: bool = False, **arguments):
        """Execute any registered tool through the central permission-aware executor."""
        return await tool_executor.execute(
            tool_name=tool_name,
            arguments=arguments,
            agent=agent,
            confirmed=confirmed,
        )


tool_runtime = ToolRuntime()
