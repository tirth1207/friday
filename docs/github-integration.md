# FRIDAY GitHub Integration

FRIDAY has two layers for GitHub:

1. Dedicated semantic tools for common read operations.
2. `github.api` for REST operations that do not have a dedicated wrapper.

## Authentication

Set these values in `.env`:

```env
GITHUB_USERNAME=your_github_username
GITHUB_PAT=your_github_personal_access_token
GITHUB_API_VERSION=2022-11-28
```

Use a fine-grained GitHub token with only the repository permissions FRIDAY needs. Keep the token server-side and never expose it to the model or UI.

## Dedicated tools

| Tool | Purpose |
| --- | --- |
| `github.profile` | Authenticated or public profile metadata |
| `github.repositories` | Repositories accessible to the authenticated account |
| `github.repository` | One repository's metadata |
| `github.commits` | Recent commits |
| `github.contents` | File or directory contents |
| `github.file.read` | UTF-8 file contents |
| `github.directory.list` | Directory entries |
| `github.file.metadata` | File metadata without body |
| `github.tree` | Recursive Git tree |
| `github.code.search` | Code search, optionally scoped to a repository |
| `github.branches` | Repository branches |
| `github.commit` | Commit metadata, stats and changed-file patches |
| `github.api` | Generic GitHub REST API escape hatch |

## Canonical arguments

FRIDAY's internal tool schemas use `repository`, not `repo_full_name` or `repo`.

Example:

```json
{
  "repository": "owner/repository",
  "recursive": true
}
```

The structured-agent compatibility layer also accepts common model aliases such as `repo_full_name`, `repo`, `branch`, and `file_path`, then normalizes them to the canonical schema.

## Repository analysis workflow

For a request such as:

> explain my project from GitHub

FRIDAY should:

1. Resolve the repository.
2. Fetch `github.repository` metadata.
3. Fetch `github.tree` recursively.
4. Read important entry points and configuration files discovered in the tree.
5. Ignore a missing README instead of failing the analysis.
6. Produce a grounded architecture explanation.

FRIDAY must never substitute local workspace files for a remote GitHub repository request.

## Generic REST API

`github.api` accepts:

- `GET`
- `POST`
- `PUT`
- `PATCH`
- `DELETE`

Example read:

```json
{
  "method": "GET",
  "path": "/repos/owner/repository/releases"
}
```

Example mutation:

```json
{
  "method": "POST",
  "path": "/repos/owner/repository/issues",
  "body": {
    "title": "Example issue"
  }
}
```

GET requests are safe. Mutating requests require explicit runtime confirmation.

## Provider tool calling

NVIDIA/LangChain tool calling requires a tool-capable model. FRIDAY sanitizes internal dotted tool names before sending them to the provider:

```text
filesystem.list  -> filesystem__list
github.file.read  -> github__file__read
github.tree       -> github__tree
```

The names are mapped back before execution. If a provider emits a JSON-shaped tool call as normal text, FRIDAY parses and executes it instead of displaying the JSON to the user.

## API behavior

GitHub REST requests use the versioned API header and authenticated Bearer token. Errors include the GitHub HTTP status and API message. Repository and file results are normalized before reaching the model, and file output is bounded to avoid oversized prompts.

GitHub's REST API has primary and secondary rate limits. FRIDAY should avoid unnecessary repeated requests, use dedicated endpoints where possible, and surface rate-limit failures rather than fabricating data.
