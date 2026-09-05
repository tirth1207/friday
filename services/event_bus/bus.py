import asyncio

from core.events import FridayEvent


class EventBus:

    def __init__(self):

        self.subscribers: set[
            asyncio.Queue
        ] = set()


    def subscribe(self):

        queue = asyncio.Queue()

        self.subscribers.add(queue)

        print(
            f"[EVENT BUS] Subscriber added. "
            f"Total: {len(self.subscribers)}"
        )

        return queue


    def unsubscribe(self, queue):

        self.subscribers.discard(queue)

        print(
            f"[EVENT BUS] Subscriber removed. "
            f"Total: {len(self.subscribers)}"
        )


    async def publish(
        self,
        event: FridayEvent,
    ):

        print(
            f"[EVENT BUS] "
            f"{event.type}: "
            f"{event.title}"
        )

        for queue in list(
            self.subscribers
        ):

            try:

                await queue.put(event)

            except Exception as error:

                print(
                    f"[EVENT BUS] "
                    f"Failed to publish: {error}"
                )


event_bus = EventBus()