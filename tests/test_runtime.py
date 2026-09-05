import pytest
import asyncio
import os
from pathlib import Path

import tools  # registers tools
from core.orchestrator import ask_friday, is_simple_conversational
from core.runtime.executor import tool_executor
from core.runtime.permissions import validate_workspace_path, get_workspace_root


@pytest.mark.asyncio
async def test_simple_conversation():
    assert is_simple_conversational("hi who are you") is True
    assert is_simple_conversational("what is recursion") is True


@pytest.mark.asyncio
async def test_filesystem_list():
    res = await tool_executor.execute("filesystem.list", {"path": "."})
    assert isinstance(res, list)
    names = [item["name"] for item in res]
    assert "core" in names
    assert "tools" in names


@pytest.mark.asyncio
async def test_filesystem_search():
    res = await tool_executor.execute("filesystem.search", {"query": "AgentRuntime", "path": "."})
    assert isinstance(res, list)
    assert any("core/agents/runtime.py" in p for p in res)


@pytest.mark.asyncio
async def test_filesystem_read():
    res = await tool_executor.execute("filesystem.read", {"path": "core/main.py"})
    assert "FastAPI" in res


@pytest.mark.asyncio
async def test_create_and_verify():
    test_file = "friday_agent_test.txt"
    test_content = "FRIDAY REAL AGENT TEST SUCCESSFUL"

    # Create file
    create_res = await tool_executor.execute(
        "filesystem.create",
        {"path": test_file, "content": test_content, "overwrite": True}
    )
    assert "created" in create_res.lower()

    # Verify file physically exists
    filepath = get_workspace_root() / test_file
    assert filepath.exists()

    # Read file back
    read_res = await tool_executor.execute("filesystem.read", {"path": test_file})
    assert read_res == test_content

    # Clean up
    if filepath.exists():
        os.remove(filepath)


@pytest.mark.asyncio
async def test_security_path_traversal():
    with pytest.raises(PermissionError):
        validate_workspace_path("../../etc/passwd")

    with pytest.raises(PermissionError):
        validate_workspace_path(".env")
