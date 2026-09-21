from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.config import settings
from core.events import FridayEvent
from core.memory import memory_store
from core.proactive.attention import AttentionManager
from core.proactive.models import ProactiveSignal
from services.event_bus.bus import event_bus

_NOOP_MARKERS = {"NOOP", "NONE", "NOTHING", "NO_MESSAGE"}


def _is_noop(response: str) -> bool:
    first = (response or "").strip().splitlines()[0].strip().upper() if response else ""
    return not response.strip() or first in _NOOP_MARKERS


class CognitionLoop:
    """Periodic bounded self-check using FRIDAY's existing model."""

    def __init__(self, interval_seconds: int | None = None):
        self.interval_seconds = max(
            300,
            int(interval_seconds or settings.proactive_cognition_interval_seconds),
        )
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if not settings.proactive_cognition_enabled or not settings.proactive_enabled:
            return
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="friday-cognition-loop")

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
        await asyncio.sleep(max(0, settings.proactive_initial_delay_seconds))
        while self._running:
            try:
                await self.cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[FRIDAY cognition] cycle failed: {type(exc).__name__}: {exc}")
            await asyncio.sleep(self.interval_seconds)

    async def cycle(self) -> str | None:
        from core.orchestrator_structured import ask_friday

        recent = memory_store.get_recent_messages(12)
        experiences = memory_store.search_experiences("", 6)
        context = "\n".join(
            f"{item['role']}: {item['content'][:800]}" for item in recent
        ) or "(no recent conversation)"
        lessons = "\n".join(
            f"- {item['title']}: {item['lesson'][:500]}" for item in experiences
        ) or "(no saved lessons)"

        prompt = f"""You are running FRIDAY's periodic attention check for Tirth.

Your job is NOT to chat. Decide whether there is one concrete, useful thing
Tirth should know right now based only on the supplied local context.

Recent conversation:
{context}

Recent lessons:
{lessons}

Rules:
- Do not invent external facts.
- Do not expose hidden reasoning.
- Do not repeat ordinary conversation.
- Do not interrupt for trivial information.
- If nothing is worth interrupting Tirth about, return exactly: NOOP
- Otherwise return a concise message addressed to Tirth, beginning with the
  useful fact/question. No preamble about being an AI."""

        response = await ask_friday(prompt)
        if _is_noop(response):
            return None

        summary = response.strip()
        signal = ProactiveSignal(
            source="cognition",
            kind="periodic_attention_check",
            title="FRIDAY has an update",
            summary=summary,
            importance=0.70,
            urgency=0.45,
            relevance=0.92,
            confidence=0.72,
            dedupe_key=AttentionManager.make_dedupe_key(
                "cognition", "periodic_attention_check",
                "FRIDAY has an update", summary,
            ),
            payload={"generated_at": datetime.now(timezone.utc).isoformat()},
        )

        from core.proactive.runtime import proactive_runtime
        decision = proactive_runtime.engine.attention.evaluate(signal)
        message = proactive_runtime.engine.attention.record(signal, decision)
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
        return summary
