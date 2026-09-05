from core.events import FridayEvent
from services.event_bus.bus import event_bus

from tools.filesystem.list import list_directory
from tools.filesystem.search import search_files
from tools.filesystem.read import read_file


class ToolRuntime:

    async def emit(
        self,
        event_type,
        title,
        description=None,
        agent=None,
        tool=None,
        status=None,
        metadata=None,
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


    async def execute(
        self,
        tool_name: str,
        agent: str,
        **arguments,
    ):

        await self.emit(
            "tool_started",
            f"{tool_name} started",
            f"Executing {tool_name}",
            agent=agent,
            tool=tool_name,
            status="running",
        )

        try:

            if tool_name == "filesystem.list":

                result = await list_directory(
                    arguments["directory"]
                )

            elif tool_name == "filesystem.search":

                result = await search_files(
                    arguments["directory"],
                    arguments["query"],
                )

            elif tool_name == "filesystem.read":

                result = await read_file(
                    arguments["file_path"]
                )

            else:

                raise ValueError(
                    f"Unknown tool: {tool_name}"
                )


            safe_metadata = {}

            if isinstance(result, list):

                safe_metadata = {
                    "count": len(result),
                    "results": result[:20],
                }

            elif isinstance(result, str):

                safe_metadata = {
                    "characters": len(result),
                }

            else:

                safe_metadata = {
                    "result": str(result)[:1000],
                }


            await self.emit(
                "tool_completed",
                f"{tool_name} completed",
                "Tool execution completed successfully.",
                agent=agent,
                tool=tool_name,
                status="success",
                metadata=safe_metadata,
            )

            return result


        except Exception as error:

            await self.emit(
                "tool_error",
                f"{tool_name} failed",
                str(error),
                agent=agent,
                tool=tool_name,
                status="failed",
                metadata={
                    "error": str(error)[:500],
                },
            )

            raise


tool_runtime = ToolRuntime()
