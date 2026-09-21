from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from core.events import FridayEvent
from core.proactive.attention import AttentionManager
from core.proactive.models import ProactiveSignal
from services.event_bus.bus import event_bus

SignalHandler = Callable[[FridayEvent], Awaitable[ProactiveSignal | None]]


class ProactiveEngine:
    """Event-driven proactive loop.

    It is intentionally conservative: event -> signal -> attention gate ->
    notification. Future LLM/OSIRIS observers can plug in as signal handlers.
    """

    def __init__(self, attention: AttentionManager | None = None):
        self.attention = attention or AttentionManager()
        self.handlers: list[SignalHandler] = []
        self._task: asyncio.Task | None = None
        self._running = False

    def register(self, handler: SignalHandler) -> None:
        self.handlers.append(handler)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="friday-proactive-engine")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        queue = event_bus.subscribe()
        try:
            while self._running:
                event = await queue.get()
                await self.process_event(event)
        finally:
            event_bus.unsubscribe(queue)

    async def process_event(self, event: FridayEvent) -> list:
        messages = []
        for handler in list(self.handlers):
            try:
                signal = await handler(event)
                if not signal:
                    continue
                decision = self.attention.evaluate(signal)
                message = self.attention.record(signal, decision)
                if message:
                    messages.append(message)
                    await event_bus.publish(
                        FridayEvent(
                            type="proactive_message",
                            title=message.title,
                            description=message.message,
                            status=message.level.value,
                            metadata={
                                "message_id": message.id,
                                "signal_id": message.signal_id,
                                "source": message.source,
                                "score": decision.score,
                            },
                        )
                    )
            except Exception as exc:
                await event_bus.publish(
                    FridayEvent(
                        type="error",
                        title="Proactive observer failed",
                        description=f"{type(exc).__name__}: {exc}",
                        status="observer_error",
                        metadata={"event_type": event.type},
                    )
                )
        return messages
