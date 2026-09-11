import pytest

from providers.nvidia.client import FridayAgentModel


class SyncModel:
    def invoke(self, value, config=None, **kwargs):
        return {"content": "hello"}


class AsyncModel:
    async def invoke(self, value, config=None, **kwargs):
        return {"content": "hello"}


@pytest.mark.asyncio
async def test_nvidia_adapter_accepts_sync_invoke_result():
    result = await FridayAgentModel(SyncModel()).ainvoke("hello")
    assert result == {"content": "hello"}


@pytest.mark.asyncio
async def test_nvidia_adapter_accepts_awaitable_invoke_result():
    result = await FridayAgentModel(AsyncModel()).ainvoke("hello")
    assert result == {"content": "hello"}
