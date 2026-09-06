from core.runtime.langchain_tools import get_langchain_tools, tool_names


def test_all_registered_tools_are_exposed_to_langchain():
    names = tool_names()

    assert "github.repository" in names
    assert "github.tree" in names
    assert "github.file.read" in names
    assert "github.code.search" in names
    assert "github.api" in names
    assert "filesystem.read" in names
    assert "terminal.execute" in names
    assert "os.system_info" in names


def test_langchain_tool_schemas_have_names_and_descriptions():
    tools = get_langchain_tools()

    assert tools
    for tool in tools:
        assert tool.name
        assert tool.description
        assert tool.args_schema is not None


def test_github_tools_use_repository_argument_schema():
    tools = {tool.name: tool for tool in get_langchain_tools()}

    assert "repository" in tools["github.repository"].args_schema.model_fields
    assert "repository" in tools["github.tree"].args_schema.model_fields
    assert "repository" in tools["github.file.read"].args_schema.model_fields
