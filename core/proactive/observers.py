from __future__ import annotations

from core.events import FridayEvent
from core.proactive.attention import AttentionManager
from core.proactive.models import ProactiveSignal


async def execution_observer(event: FridayEvent) -> ProactiveSignal | None:
    """Turn important execution failures/completions into attention candidates."""
    if event.type == "tool_error":
        title = event.title or "FRIDAY tool failure"
        summary = event.description or "A FRIDAY tool failed during execution."
        return ProactiveSignal(
            source="execution",
            kind="tool_error",
            title=title,
            summary=f"I noticed an execution problem: {summary}",
            importance=0.72,
            urgency=0.70,
            relevance=0.85,
            confidence=0.95,
            dedupe_key=AttentionManager.make_dedupe_key(
                "execution", "tool_error", title, summary
            ),
            payload=event.metadata,
        )

    if event.type == "verification" and event.status in {"failed", "error"}:
        summary = event.description or "Verification failed."
        return ProactiveSignal(
            source="execution",
            kind="verification_failed",
            title="FRIDAY verification failed",
            summary=f"I verified the task and found a failure: {summary}",
            importance=0.82,
            urgency=0.75,
            relevance=0.90,
            confidence=0.90,
            dedupe_key=AttentionManager.make_dedupe_key(
                "execution", "verification_failed", event.title, summary
            ),
            payload=event.metadata,
        )

    return None


async def explicit_question_observer(event: FridayEvent) -> ProactiveSignal | None:
    """Convert events explicitly marked as needing Tirth's input into a message."""
    if event.metadata.get("requires_user_input") is not True:
        return None

    summary = event.description or "FRIDAY needs your input."
    return ProactiveSignal(
        source="friday",
        kind="user_input_required",
        title=event.title or "FRIDAY needs your input",
        summary=summary,
        importance=0.80,
        urgency=float(event.metadata.get("urgency", 0.60)),
        relevance=0.95,
        confidence=0.95,
        dedupe_key=AttentionManager.make_dedupe_key(
            "friday", "user_input_required", event.title, summary
        ),
        payload=event.metadata,
    )
