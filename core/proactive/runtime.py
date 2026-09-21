from __future__ import annotations

import asyncio

from core.proactive.engine import ProactiveEngine
from core.proactive.observers import execution_observer, explicit_question_observer


class ProactiveRuntime:
    """Owns FRIDAY's background proactive engine for the FastAPI process."""

    def __init__(self):
        self.engine = ProactiveEngine()
        self.engine.register(execution_observer)
        self.engine.register(explicit_question_observer)
        self._started = False

    async def start(self):
        if self._started:
            return
        await self.engine.start()
        self._started = True
        print("[FRIDAY] Proactive intelligence runtime started")

    async def stop(self):
        if not self._started:
            return
        await self.engine.stop()
        self._started = False
        print("[FRIDAY] Proactive intelligence runtime stopped")


proactive_runtime = ProactiveRuntime()
