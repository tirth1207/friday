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
from tools.github.github_tools import github_get_profile, github_list_repositories, github_get_repository, github_list_commits
from tools.os.os_tools import os_system_info, os_list_processes, os_disk_usage, os_list_drives, os_read_file, os_write_file, os_list_directory, os_create_directory, os_path_exists, os_delete_path


def register_all_tools():
    tool_registry.register(name="filesystem.list", func=list_directory, description="List files and directories in the configured workspace.", permission=PermissionLevel.SAFE, parameters={"path": "string"})
    tool_registry.register(name="filesystem.search", func=search_files, description="Search files in the configured workspace.", permission=PermissionLevel.SAFE, parameters={"query": "string", "path": "string"})
    tool_registry.register(name="filesystem.read", func=read_file, description="Read a file in the configured workspace.", permission=PermissionLevel.SAFE, parameters={"path": "string"})
    tool_registry.register(name="filesystem.write", func=write_file, description="Write a file in the configured workspace.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "content": "string"})
    tool_registry.register(name="filesystem.create", func=create_file, description="Create a file in the configured workspace.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "content": "string", "overwrite": "boolean"})
    tool_registry.register(name="filesystem.exists", func=file_exists, description="Check a workspace path.", permission=PermissionLevel.SAFE, parameters={"path": "string"})

    tool_registry.register(name="terminal.execute", func=execute_command, description="Execute a terminal command in the workspace.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"command": "string", "timeout": "number"})

    tool_registry.register(name="git.status", func=git_status, description="Get Git working tree status.", permission=PermissionLevel.SAFE)
    tool_registry.register(name="git.diff", func=git_diff, description="Get Git working tree diff.", permission=PermissionLevel.SAFE)
    tool_registry.register(name="git.log", func=git_log, description="Get Git commit history.", permission=PermissionLevel.SAFE, parameters={"max_count": "number"})
    tool_registry.register(name="git.branch", func=git_branch, description="Get Git branches.", permission=PermissionLevel.SAFE)

    tool_registry.register(name="github.profile", func=github_get_profile, description="Fetch GitHub profile using configured credentials.", permission=PermissionLevel.SAFE, parameters={"username": "string"})
    tool_registry.register(name="github.repositories", func=github_list_repositories, description="List repositories for the configured GitHub user.", permission=PermissionLevel.SAFE, parameters={"username": "string", "limit": "number", "sort": "string"})
    tool_registry.register(name="github.repository", func=github_get_repository, description="Fetch one GitHub repository's metadata.", permission=PermissionLevel.SAFE, parameters={"repository": "string"})
    tool_registry.register(name="github.commits", func=github_list_commits, description="Fetch recent commits for a GitHub repository.", permission=PermissionLevel.SAFE, parameters={"repository": "string", "limit": "number"})

    tool_registry.register(name="os.system_info", func=os_system_info, description="Inspect operating-system and host information.", permission=PermissionLevel.SAFE)
    tool_registry.register(name="os.processes", func=os_list_processes, description="List running processes without command-line arguments.", permission=PermissionLevel.SAFE, parameters={"limit": "number"})
    tool_registry.register(name="os.disk_usage", func=os_disk_usage, description="Inspect disk capacity and usage for a local path.", permission=PermissionLevel.SAFE, parameters={"path": "string"})
    tool_registry.register(name="os.drives", func=os_list_drives, description="List all mounted drives and partitions accessible to FRIDAY.", permission=PermissionLevel.SAFE)

    # Cross-drive OS filesystem. Absolute paths are supported on every accessible drive.
    tool_registry.register(name="os.file.read", func=os_read_file, description="Read a text file from any accessible local drive or absolute path.", permission=PermissionLevel.SAFE, parameters={"path": "string"})
    tool_registry.register(name="os.file.write", func=os_write_file, description="Write a UTF-8 text file to any accessible local drive or absolute path.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "content": "string", "overwrite": "boolean"})
    tool_registry.register(name="os.folder.list", func=os_list_directory, description="List files and folders from any accessible local drive or absolute path.", permission=PermissionLevel.SAFE, parameters={"path": "string", "include_hidden": "boolean"})
    tool_registry.register(name="os.folder.create", func=os_create_directory, description="Create a folder and missing parents on any accessible local drive.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string"})
    tool_registry.register(name="os.path.exists", func=os_path_exists, description="Check whether a file or folder exists on any accessible local drive.", permission=PermissionLevel.SAFE, parameters={"path": "string"})
    tool_registry.register(name="os.path.delete", func=os_delete_path, description="Delete a file or directory on an accessible local drive.", permission=PermissionLevel.PERMISSION_REQUIRED, parameters={"path": "string", "recursive": "boolean"})


register_all_tools()
