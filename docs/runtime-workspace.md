# FRIDAY Runtime Workspace

FRIDAY keeps its own runtime data outside every user repository.

## Default location

- Windows: `C:\.friday`
- Linux/macOS: `~/.friday`
- Override with `FRIDAY_WORKSPACE`

Repository clones live under:

`<FRIDAY_WORKSPACE>/workspaces/<owner_repo_hash>`

Filesystem, terminal, and Git developer tools are scoped to the selected clone. A repository request such as `test.txt` therefore means a file in that clone, not in FRIDAY's source tree or runtime directory.

The selected clone is the only workspace that may be modified, committed, or pushed for that task.
