from datetime import datetime, timezone, timedelta

from core.orchestrator_structured import _live_data_is_fresh


def test_live_data_is_fresh_when_timestamp_is_recent():
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    fresh, note = _live_data_is_fresh({"data": {"updated_at": recent}})
    assert fresh
    assert "hours old" in note


def test_live_data_is_stale_when_timestamp_is_old():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fresh, note = _live_data_is_fresh({"data": {"updated_at": old}})
    assert not fresh
    assert "freshness limit" in note


def test_undated_live_data_is_not_trusted():
    fresh, note = _live_data_is_fresh({"data": {"events": [{"name": "unknown"}]}})
    assert not fresh
    assert "No machine-readable freshness timestamp" in note
