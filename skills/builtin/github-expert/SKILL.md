---
name: GitHub Expert
description: Work with GitHub repositories, branches, commits, issues, pull requests, code, and repository structure. Use for GitHub analysis and repository operations.
version: 1.0.0
author: FRIDAY
license: MIT
tags: [github, git, repository, repo, commit, branch, issue, pull-request, code]
triggers: [github, github.com, repository, repo, commit, branch, pull request, issue]
capabilities:
  filesystem: false
  network: true
  shell: false
  secrets: true
trusted: true
priority: 12
---

# GitHub Expert

Use the registered GitHub tools for GitHub data and operations. Inspect repository state before mutations. Never expose tokens, credentials, or secret values. Prefer read-only operations for analysis and use the existing permission/confirmation flow for writes.

For repository questions, resolve the exact repository before acting. For code questions, prefer the smallest relevant files and use repository tree/file tools rather than guessing paths.
