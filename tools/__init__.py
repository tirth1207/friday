from core.runtime.permissions import PermissionLevel
from core.runtime.registry import tool_registry

from tools.filesystem.list import list_directory
from tools.filesystem.search import search_files
from tools.filesystem.read import read_file
from tools.filesystem.write import write_file
from tools.filesystem.create import create_file
from tools.filesystem.exists import file_exists

from tools.terminal.execute import execute_command
from tools.git.git_tools import git_status, git_diff, git_log, git_branch
from tools.github.github_tools import (
    github_get_profile,
    github_list_repositories,
    github_get_repository,
    github_list_commits,
)
from tools.os.os_tools import (
    os_system_info,
    os_list_processes,
    os_disk_usage,
    os_current_directory,
)


def register_all_tools():
    tool_registry.register(
        name="filesystem.list", func=list_directory,
        description="List files and directories at path in workspace.",
        permission=PermissionLevel.SAFE, parameters={"path": "string"},
    )
    tool_registry.register(
        name="filesystem.search", func=search_files,
        description="Search workspace files matching query by filename or text content.",
        permission=PermissionLevel.SAFE, parameters={"query": "string", "path": "string"},
    )
    tool_registry.register(
        name="filesystem.read", func=read_file,
        description="Read file contents relative to workspace.",
        permission=PermissionLevel.SAFE, parameters={"path": "string"},
    )
    tool_registry.register(
        name="filesystem.write", func=write_file,
        description="Write or overwrite content to a file in workspace.",
        permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "content": "string"},
    )
    tool_registry.register(
        name="filesystem.create", func=create_file,
        description="Create a new file in workspace with content.",
        permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "content": "string", "overwrite": "boolean"},
    )
    tool_registry.register(
        name="filesystem.exists", func=file_exists,
        description="Check if a path exists in workspace.",
        permission=PermissionLevel.SAFE, parameters={"path": "string"},
    )

    tool_registry.register(
        name="terminal.execute", func=execute_command,
        description="Execute terminal command safely in workspace.",
        permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"command": "string", "timeout": "number"},
    )

    tool_registry.register(
        name="git.status", func=git_status,
        description="Get git working tree status.", permission=PermissionLevel.SAFE,
    )
    tool_registry.register(
        name="git.diff", func=git_diff,
        description="Get git working tree diff.", permission=PermissionLevel.SAFE,
    )
    tool_registry.register(
        name="git.log", func=git_log,
        description="Get git commit history log.", permission=PermissionLevel.SAFE, parameters={"max_count": "number"},
    )
    tool_registry.register(
        name="git.branch", func=git_branch,
        description="Get list of git branches.", permission=PermissionLevel.SAFE,
    )

    # GitHub data tools. PAT is read only from the server environment.
    tool_registry.register(
        name="github.profile", func=github_get_profile,
        description="Fetch GitHub profile data using configured credentials.",
        permission=PermissionLevel.SAFE, parameters={"username": "string"},
    )
    tool_registry.register(
        name="github.repositories", func=github_list_repositories,
        description="List repositories for the configured GitHub user.",
        permission=PermissionLevel.SAFE, parameters={"username": "string", "limit": "number", "sort": "string"},
    )
    tool_registry.register(
        name="github.repository", func=github_get_repository,
        description="Fetch detailed metadata for one GitHub repository.",
        permission=PermissionLevel.SAFE, parameters={"repository": "string"},
    )
    tool_registry.register(
        name="github.commits", func=github_list_commits,
        description="Fetch recent commits for a GitHub repository.",
        permission=PermissionLevel.SAFE, parameters={"repository": "string", "limit": "number"},
    )

    # Safe OS inspection tools. Arbitrary command execution stays behind terminal.execute.
    tool_registry.register(
        name="os.system_info", func=os_system_info,
        description="Inspect safe operating-system, host, CPU, memory, Python, and working-directory information.",
        permission=PermissionLevel.SAFE,
    )
    tool_registry.register(
        name="os.processes", func=os_list_processes,
        description="List running processes without command-line arguments or environment variables.",
        permission=PermissionLevel.SAFE, parameters={"limit": "number"},
    )
    tool_registry.register(
        name="os.disk_usage", func=os_disk_usage,
        description="Inspect disk capacity and usage for a local path.",
        permission=PermissionLevel.SAFE, parameters={"path": "string"},
    )
    tool_registry.register(
        name="os.cwd", func=os_current_directory,
        description="Return FRIDAY's current working directory.", permission=PermissionLevel.SAFE,
    )


register_all_tools()
