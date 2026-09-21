import pytest

from core import tier0


@pytest.mark.asyncio
async def test_time_request_does_not_require_an_ai_provider():
    result = await tier0.handle("what time is it?")
    assert result is not None
    assert "(IST)" in result


@pytest.mark.asyncio
async def test_date_request_is_deterministic():
    result = await tier0.handle("what's today's date?")
    assert result is not None
    assert "2026" in result


@pytest.mark.asyncio
async def test_unknown_request_falls_through():
    result = await tier0.handle("explain why my architecture is failing")
    assert result is None


@pytest.mark.asyncio
async def test_provider_health_request_uses_health_state(monkeypatch):
    monkeypatch.setattr(
        tier0,
        "nvidia_health_snapshot",
        lambda: {
            "status": "degraded",
            "consecutive_failures": 3,
            "last_error": "503 overloaded",
        },
    )
    result = await tier0.handle("provider health")
    assert result is not None
    assert "degraded" in result
    assert "503 overloaded" in result


@pytest.mark.asyncio
async def test_system_info_is_delegated_to_safe_tool(monkeypatch):
    calls = []

    async def fake_execute(tool_name, arguments, agent):
        calls.append((tool_name, arguments, agent))
        return {"platform": "test", "cpu": "test-cpu"}

    monkeypatch.setattr(tier0.tool_executor, "execute", fake_execute)
    result = await tier0.handle("system info")

    assert result is not None
    assert "test-cpu" in result
    assert calls == [("os.system_info", {}, "Tier-0 Reflex")]
