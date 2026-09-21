from core.proactive.attention import AttentionManager
from core.proactive.models import AttentionLevel, ProactiveSignal


def test_low_signal_is_silent(tmp_path):
    manager = AttentionManager(str(tmp_path / "proactive.db"))
    signal = ProactiveSignal(
        source="test",
        kind="noise",
        title="Noise",
        summary="Ignore this.",
        importance=0.1,
        urgency=0.0,
        relevance=0.1,
        confidence=0.5,
        dedupe_key="noise-1",
    )
    decision = manager.evaluate(signal)
    assert decision.level == AttentionLevel.QUIET
    assert not decision.should_deliver


def test_urgent_signal_is_delivered(tmp_path):
    manager = AttentionManager(str(tmp_path / "proactive.db"))
    signal = ProactiveSignal(
        source="test",
        kind="incident",
        title="Build failed",
        summary="The production build failed.",
        importance=1.0,
        urgency=1.0,
        relevance=1.0,
        confidence=1.0,
        dedupe_key="incident-1",
    )
    decision = manager.evaluate(signal)
    assert decision.level == AttentionLevel.URGENT
    message = manager.record(signal, decision)
    assert message is not None
    assert manager.recent(1)[0]["title"] == "Build failed"


def test_duplicate_is_quiet(tmp_path):
    manager = AttentionManager(str(tmp_path / "proactive.db"))
    signal = ProactiveSignal(
        source="test",
        kind="incident",
        title="Same",
        summary="Same",
        importance=1.0,
        urgency=1.0,
        relevance=1.0,
        confidence=1.0,
        dedupe_key="same",
    )
    decision = manager.evaluate(signal)
    manager.record(signal, decision)
    duplicate = manager.evaluate(signal.model_copy(update={"id": "second"}))
    assert duplicate.level == AttentionLevel.QUIET
