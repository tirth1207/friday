from core.runtime.langchain_tools import get_langchain_tools, registry_tool_name, tool_names


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


def test_provider_tool_names_are_safe():
    tools = get_langchain_tools()

    assert tools
    for tool in tools:
        assert tool.name
        assert tool.description
        assert tool.args_schema is not None
        assert all(char.isalnum() or char in "_-" for char in tool.name)


def test_dotted_names_round_trip():
    assert registry_tool_name("github__tree") == "github.tree"
    assert registry_tool_name("filesystem__list") == "filesystem.list"
    assert registry_tool_name("os__path__exists") == "os.path.exists"


def test_github_tools_use_repository_argument_schema():
    tools = {tool.name: tool for tool in get_langchain_tools()}

    assert "github__repository" in tools
    assert "github__tree" in tools
    assert "github__file__read" in tools
    assert "repository" in tools["github__repository"].args_schema.model_fields
    assert "repository" in tools["github__tree"].args_schema.model_fields
    assert "repository" in tools["github__file__read"].args_schema.model_fields
