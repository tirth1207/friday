from __future__ import annotations

import asyncio

from core.config import settings
from core.events import FridayEvent
from core.proactive.cognition import CognitionLoop
from core.proactive.engine import ProactiveEngine
from core.proactive.observers import execution_observer, explicit_question_observer
from core.proactive.osiris_watcher import poll_due_interests
from services.event_bus.bus import event_bus


class ProactiveRuntime:
    """Owns FRIDAY's event-driven, OSIRIS and periodic proactive intelligence."""

    def __init__(self):
        self.engine = ProactiveEngine()
        self.engine.register(execution_observer)
        self.engine.register(explicit_question_observer)
        self.cognition = CognitionLoop()
        self._osiris_task: asyncio.Task | None = None
        self._started = False

    async def start(self):
        if self._started:
            return
        await self.engine.start()
        await self.cognition.start()
        if settings.proactive_enabled and settings.proactive_osiris_enabled:
            self._osiris_task = asyncio.create_task(self._osiris_loop(), name="friday-osiris-watcher")
        self._started = True
        print("[FRIDAY] Proactive intelligence runtime started")

    async def stop(self):
        if not self._started:
            return
        await self.cognition.stop()
        await self.engine.stop()
        if self._osiris_task:
            self._osiris_task.cancel()
            try:
                await self._osiris_task
            except asyncio.CancelledError:
                pass
            self._osiris_task = None
        self._started = False
        print("[FRIDAY] Proactive intelligence runtime stopped")

    async def _osiris_loop(self):
        await asyncio.sleep(max(5, settings.proactive_initial_delay_seconds))
        while True:
            try:
                signals = await poll_due_interests(self.engine.attention)
                for signal in signals:
                    decision = self.engine.attention.evaluate(signal)
                    message = self.engine.attention.record(signal, decision)
                    if message:
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
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await event_bus.publish(
                    FridayEvent(
                        type="error",
                        title="OSIRIS watcher failed",
                        description=f"{type(exc).__name__}: {exc}",
                        status="osiris_watcher_error",
                    )
                )
            await asyncio.sleep(max(300, settings.proactive_osiris_interval_seconds))


proactive_runtime = ProactiveRuntime()
