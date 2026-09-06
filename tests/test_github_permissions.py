import pytest

import tools  # registers tools
from core.runtime.executor import tool_executor


@pytest.mark.asyncio
async def test_github_get_is_safe():
    # This may reach the configured GitHub API when credentials are available.
    # The important contract is that GET is not blocked by confirmation policy.
    result = await tool_executor.execute(
        "github.api",
        {"method": "GET", "path": "/rate_limit"},
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_github_mutation_requires_confirmation():
    with pytest.raises(PermissionError, match="requires explicit confirmation"):
        await tool_executor.execute(
            "github.api",
            {
                "method": "POST",
                "path": "/repos/example/example/issues",
                "body": {"title": "should not be sent"},
            },
        )
